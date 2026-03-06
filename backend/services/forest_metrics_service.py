from __future__ import annotations

import json
import logging
import os
from hashlib import sha1
from typing import Any

from sqlalchemy import text

from api.db import get_engine
from api.schemas import (
    DemoMetricsResponse,
    ForecastPoint,
    ForestMetricsResponse,
    HealthForecastResponse,
    HealthScoreResponse,
    NDVIMapResponse,
    RiskAlert,
    RiskAlertsResponse,
    RiskZonesResponse,
    SpeciesCompositionResponse,
    SystemStatusResponse,
    TreeDensityResponse,
)
logger = logging.getLogger(__name__)


class ForestMetricsService:
    def __init__(self) -> None:
        from services.ml_bridge import MLBridge
        from services.region_pipeline_service import RegionPipelineService

        self.ml = MLBridge.get_instance()
        self.region_pipeline = RegionPipelineService()
        self.demo_cache_enabled = os.getenv("DEMO_CACHE_ENABLED", "true").lower() == "true"
        self.trigger_pipeline_on_request = (
            os.getenv("REGION_PIPELINE_TRIGGER_ON_REQUEST", "false").lower() == "true"
        )

    def _prepare_region_data(self, polygon: list[list[float]]) -> None:
        if not self.trigger_pipeline_on_request:
            return
        try:
            logger.info("Region pipeline trigger enabled; running for polygon=%s", self._polygon_fingerprint(polygon))
            result = self.region_pipeline.run_for_polygon(polygon)
            logger.info("Region pipeline run result (polygon=%s): %s", self._polygon_fingerprint(polygon), result)
        except Exception as exc:
            logger.warning("Region pipeline failed for polygon request: %s", exc)

    def _polygon_fingerprint(self, polygon: list[list[float]]) -> str:
        canonical = json.dumps(polygon, separators=(",", ":"), ensure_ascii=False)
        return sha1(canonical.encode("utf-8")).hexdigest()[:10]

    # ── DB Helpers ───────────────────────────────────────────────────────

    def _fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        engine = get_engine()
        if engine is None:
            logger.warning("Database engine unavailable for single-row query")
            return None
        try:
            with engine.connect() as connection:
                row = connection.execute(text(query), params or {}).mappings().first()
                return dict(row) if row else None
        except Exception as exc:
            logger.warning("Single-row query failed: %s", exc)
            return None

    def _fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        engine = get_engine()
        if engine is None:
            logger.warning("Database engine unavailable for multi-row query")
            return []
        try:
            with engine.connect() as connection:
                rows = connection.execute(text(query), params or {}).mappings().all()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.warning("Multi-row query failed: %s", exc)
            return []

    def _area_km2(self, polygon: list[list[float]]) -> float:
        return round(max(len(polygon) - 2, 1) * 0.85, 2)

    def _get_demo_cached_forest_metrics(
        self,
        polygon: list[list[float]],
    ) -> ForestMetricsResponse | None:
        row = self._fetch_one(
            """
            SELECT response
            FROM demo_polygon_cache
            WHERE ST_Equals(polygon, json_polygon_to_geom(CAST(:polygon AS jsonb)))
            LIMIT 1
            """,
            {"polygon": json.dumps(polygon)},
        )
        if not row:
            return None

        payload = row.get("response")
        if not isinstance(payload, dict):
            return None

        species_distribution = payload.get("species_distribution") or {}
        if not isinstance(species_distribution, dict):
            species_distribution = {}

        normalized_species_distribution = {
            "teak": float(species_distribution.get("teak") or 0),
            "bamboo": float(species_distribution.get("bamboo") or 0),
            "mixed_deciduous": float(species_distribution.get("mixed_deciduous") or 0),
        }

        return ForestMetricsResponse(
            area_km2=float(payload.get("area_km2") or 0),
            tree_count=int(round(float(payload.get("tree_count") or 0))),
            tree_density=float(payload.get("tree_density") or 0),
            health_score=float(payload.get("health_score") or 0),
            risk_level=str(payload.get("risk_level") or "Low"),
            species_distribution=normalized_species_distribution,
            forecast_health=float(payload.get("forecast_health") or 0),
        )

    # ── /forest-metrics ──────────────────────────────────────────────────

    def get_forest_metrics(self, polygon: list[list[float]]) -> ForestMetricsResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Forest metrics requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        if self.demo_cache_enabled:
            demo_cached = self._get_demo_cached_forest_metrics(polygon)
            if demo_cached is not None:
                logger.info("Forest metrics served from demo cache (polygon=%s)", polygon_fp)
                return demo_cached

        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT *
            FROM get_forest_metrics(CAST(:polygon AS jsonb))
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and row.get("tree_density") and row.get("tree_density") > 0:
            species_distribution = row.get("species_distribution") or {}
            if not isinstance(species_distribution, dict):
                species_distribution = {}
            normalized_species_distribution = {
                "teak": float(species_distribution.get("teak") or 0),
                "bamboo": float(species_distribution.get("bamboo") or 0),
                "mixed_deciduous": float(species_distribution.get("mixed_deciduous") or 0),
            }
            logger.info("Forest metrics served from database function get_forest_metrics (polygon=%s)", polygon_fp)
            return ForestMetricsResponse(
                area_km2=float(row.get("area_km2") or 0),
                tree_count=int(round(float(row.get("tree_count") or 0))),
                tree_density=float(row.get("tree_density") or 0),
                health_score=float(row.get("health_score") or 0),
                risk_level=str(row.get("risk_level") or "Low"),
                species_distribution=normalized_species_distribution,
                forecast_health=float(row.get("forecast_health") or 0),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        logger.warning("Forest metrics fallback to ML bridge (polygon=%s)", polygon_fp)
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        tree_count = self.ml.calculate_total_trees(tree_density, area_km2)
        health_score = float(self.ml.compute_health())
        risk_raw = self.ml.detect_risk()
        risk_level = self.ml.classify_risk_level(risk_raw)
        forecast_points = self.ml.forecast_as_monthly_points()
        forecast_health = float(forecast_points[0]["health_score"]) if forecast_points else health_score

        response = ForestMetricsResponse(
            area_km2=area_km2,
            tree_count=tree_count,
            tree_density=tree_density,
            health_score=health_score,
            risk_level=risk_level,
            species_distribution={"teak": 58.0, "bamboo": 27.0, "mixed_deciduous": 15.0},
            forecast_health=forecast_health,
        )
        logger.info(
            "Forest metrics ML fallback result (polygon=%s, area_km2=%.2f, tree_density=%.2f, health_score=%.2f, risk_level=%s)",
            polygon_fp,
            response.area_km2,
            response.tree_density,
            response.health_score,
            response.risk_level,
        )
        return response

    # ── /tree-density ────────────────────────────────────────────────────

    def get_tree_density(self, polygon: list[list[float]]) -> TreeDensityResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Tree density requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT *
            FROM get_tree_density(CAST(:polygon AS jsonb))
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and row.get("tree_density") and row.get("tree_density") > 0:
            logger.info("Tree density served from database function get_tree_density (polygon=%s)", polygon_fp)
            return TreeDensityResponse(
                tree_density=float(row.get("tree_density") or 0),
                total_trees=int(round(float(row.get("total_trees") or 0))),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        logger.warning("Tree density fallback to ML bridge (polygon=%s)", polygon_fp)
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        total_trees = self.ml.calculate_total_trees(tree_density, area_km2)
        return TreeDensityResponse(tree_density=tree_density, total_trees=total_trees)

    # ── /health-score ────────────────────────────────────────────────────

    def get_health_score(self, polygon: list[list[float]]) -> HealthScoreResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Health score requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT *
            FROM get_health_score(CAST(:polygon AS jsonb))
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and row.get("health_score") and row.get("health_score") > 0:
            logger.info("Health score served from database function get_health_score (polygon=%s)", polygon_fp)
            return HealthScoreResponse(
                health_score=float(row.get("health_score") or 0),
                ndvi_avg=float(row.get("ndvi_avg") or 0),
                ndmi_avg=float(row.get("ndmi_avg") or 0),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        logger.warning("Health score fallback to ML bridge (polygon=%s)", polygon_fp)
        ndvi_avg = 0.72
        ndmi_avg = 0.41
        health = self.ml.compute_health(ndvi_avg, ndmi_avg)
        return HealthScoreResponse(
            health_score=float(health), ndvi_avg=ndvi_avg, ndmi_avg=ndmi_avg
        )

    # ── /risk-alerts ─────────────────────────────────────────────────────

    def get_risk_alerts(self, polygon: list[list[float]]) -> RiskAlertsResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Risk alerts requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT get_risk_alerts(CAST(:polygon AS jsonb)) AS payload
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and isinstance(row.get("payload"), dict) and row["payload"].get("alerts"):
            payload = row["payload"]
            alerts_payload = payload.get("alerts") or []
            alerts = [
                RiskAlert(
                    type=str(item.get("type", "UNKNOWN")),
                    severity=item.get("severity", "Low"),
                    location=item.get("location", [0.0, 0.0]),
                )
                for item in alerts_payload
            ]
            logger.info("Risk alerts served from database function get_risk_alerts (polygon=%s)", polygon_fp)
            return RiskAlertsResponse(
                risk_level=payload.get("risk_level", "Low"),
                alerts=alerts,
            )

        # ── ML fallback ──────────────────────────────────────────────────
        logger.warning("Risk alerts fallback to ML bridge (polygon=%s)", polygon_fp)
        risk_raw = self.ml.detect_risk()
        risk_level = self.ml.classify_risk_level(risk_raw)
        severity = risk_level  # same mapping

        return RiskAlertsResponse(
            risk_level=risk_level,
            alerts=[
                RiskAlert(
                    type="NDVI_DROP",
                    severity=severity,
                    location=[20.35, 73.92],
                )
            ],
        )

    # ── /species-composition ─────────────────────────────────────────────

    def get_species_composition(self, polygon: list[list[float]]) -> SpeciesCompositionResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Species composition requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT get_species_composition(CAST(:polygon AS jsonb)) AS payload
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            logger.info("Species composition served from database function get_species_composition (polygon=%s)", polygon_fp)
            return SpeciesCompositionResponse(
                teak=float(payload.get("teak") or 0),
                bamboo=float(payload.get("bamboo") or 0),
                mixed_deciduous=float(payload.get("mixed_deciduous") or 0),
            )

        logger.warning("Species composition using static fallback values (polygon=%s)", polygon_fp)
        return SpeciesCompositionResponse(teak=58.0, bamboo=27.0, mixed_deciduous=15.0)

    # ── /health-forecast ─────────────────────────────────────────────────

    def get_health_forecast(self, polygon: list[list[float]]) -> HealthForecastResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Health forecast requested (polygon=%s, points=%d)", polygon_fp, len(polygon))
        self._prepare_region_data(polygon)

        row = self._fetch_one(
            """
            SELECT get_health_forecast(CAST(:polygon AS jsonb), 6) AS forecast
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and isinstance(row.get("forecast"), list) and len(row.get("forecast")) > 0:
            forecast = [
                ForecastPoint(
                    month=str(item.get("month", "")),
                    health_score=float(item.get("health_score") or 0),
                )
                for item in row["forecast"]
            ]
            logger.info("Health forecast served from database function get_health_forecast (polygon=%s)", polygon_fp)
            return HealthForecastResponse(forecast=forecast)

        # ── ML fallback ──────────────────────────────────────────────────
        logger.warning("Health forecast fallback to ML bridge (polygon=%s)", polygon_fp)
        points_raw = self.ml.forecast_as_monthly_points()
        forecast = [
            ForecastPoint(month=p["month"], health_score=p["health_score"])
            for p in points_raw
        ]
        return HealthForecastResponse(forecast=forecast)

    # ── /ndvi-map ────────────────────────────────────────────────────────

    def get_ndvi_map(self) -> NDVIMapResponse:
        logger.info("NDVI map endpoint requested")
        return NDVIMapResponse(tile_url="/ndvi-map")

    # ── /risk-zones ──────────────────────────────────────────────────────

    def get_risk_zones(self) -> RiskZonesResponse:
        logger.info("Risk zones requested")
        rows = self._fetch_all(
            """
            SELECT
                risk_level AS risk,
                ST_AsGeoJSON(geometry)::jsonb AS geometry
            FROM v_risk_zones
            ORDER BY metric_timestamp DESC
            LIMIT 200
            """
        )
        if rows:
            logger.info("Risk zones served from database view v_risk_zones (count=%d)", len(rows))
            return RiskZonesResponse(
                zones=[
                    {"risk": str(row.get("risk") or "Low"), "geometry": row.get("geometry")}
                    for row in rows
                ]
            )
        logger.warning("Risk zones query returned no rows")
        return RiskZonesResponse(zones=[])

    # ── /system-status ───────────────────────────────────────────────────

    def get_system_status(self) -> SystemStatusResponse:
        logger.info("System status requested")
        row = self._fetch_one("SELECT get_system_status() AS payload")
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            logger.info("System status served from database function get_system_status")
            return SystemStatusResponse(
                satellite_data_loaded=bool(payload.get("satellite_data_loaded", False)),
                feature_dataset_rows=int(payload.get("feature_dataset_rows", 0)),
                model_status=str(payload.get("model_status", "unknown")),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        ml_status = self.ml.get_status()
        logger.warning("System status fallback to ML bridge status: %s", ml_status)
        return SystemStatusResponse(
            satellite_data_loaded=True,
            feature_dataset_rows=45231,
            model_status="ml_ready" if ml_status["model_loaded"] else "ml_not_loaded",
        )

    # ── /demo-metrics ────────────────────────────────────────────────────

    def get_demo_metrics(self) -> DemoMetricsResponse:
        logger.info("Demo metrics requested")
        row = self._fetch_one(
            """
            SELECT get_demo_polygon_cache(:cache_key) AS payload
            """,
            {"cache_key": "demo_area"},
        )
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            logger.info("Demo metrics served from database cache")
            return DemoMetricsResponse(
                tree_count=int(payload.get("tree_count", 0)),
                health_score=float(payload.get("health_score", 0)),
                risk=str(payload.get("risk", "Low")),
            )

        # ── ML fallback (demo polygon: 5.1 km²) ─────────────────────────
        logger.warning("Demo metrics fallback to ML bridge")
        demo_area_km2 = 5.1
        density = self.ml.predict_density()
        tree_count = self.ml.calculate_total_trees(density, demo_area_km2)
        health = self.ml.compute_health()
        risk_raw = self.ml.detect_risk()
        risk_level = self.ml.classify_risk_level(risk_raw)

        return DemoMetricsResponse(
            tree_count=tree_count,
            health_score=float(health),
            risk=risk_level,
        )
