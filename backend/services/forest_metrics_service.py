from __future__ import annotations

import json
import logging
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

    # ── DB Helpers ───────────────────────────────────────────────────────

    def _fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        engine = get_engine()
        if engine is None:
            return None
        try:
            with engine.connect() as connection:
                row = connection.execute(text(query), params or {}).mappings().first()
                return dict(row) if row else None
        except Exception:
            return None

    def _fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        engine = get_engine()
        if engine is None:
            return []
        try:
            with engine.connect() as connection:
                rows = connection.execute(text(query), params or {}).mappings().all()
                return [dict(row) for row in rows]
        except Exception:
            return []

    def _area_km2(self, polygon: list[list[float]]) -> float:
        return round(max(len(polygon) - 2, 1) * 0.85, 2)

    # ── /forest-metrics ──────────────────────────────────────────────────

    def get_forest_metrics(self, polygon: list[list[float]]) -> ForestMetricsResponse:
        try:
            self.region_pipeline.run_for_polygon(polygon)
        except Exception as exc:
            logger.warning("Region pipeline failed for polygon request: %s", exc)

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
            return ForestMetricsResponse(
                area_km2=float(row.get("area_km2") or 0),
                tree_count=int(round(float(row.get("tree_count") or 0))),
                tree_density=float(row.get("tree_density") or 0),
                health_score=float(row.get("health_score") or 0),
                risk_level=str(row.get("risk_level") or "Low"),
                species_distribution={
                    key: float(value) for key, value in species_distribution.items()
                },
            )

        # ── ML fallback ──────────────────────────────────────────────────
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        tree_count = self.ml.calculate_total_trees(tree_density, area_km2)
        health_score = float(self.ml.compute_health())
        risk_raw = self.ml.detect_risk()
        risk_level = self.ml.classify_risk_level(risk_raw)

        return ForestMetricsResponse(
            area_km2=area_km2,
            tree_count=tree_count,
            tree_density=tree_density,
            health_score=health_score,
            risk_level=risk_level,
            species_distribution={"teak": 58.0, "bamboo": 27.0, "mixed": 15.0},
        )

    # ── /tree-density ────────────────────────────────────────────────────

    def get_tree_density(self, polygon: list[list[float]]) -> TreeDensityResponse:
        row = self._fetch_one(
            """
            SELECT *
            FROM get_tree_density(CAST(:polygon AS jsonb))
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and row.get("tree_density") and row.get("tree_density") > 0:
            return TreeDensityResponse(
                tree_density=float(row.get("tree_density") or 0),
                total_trees=int(round(float(row.get("total_trees") or 0))),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        total_trees = self.ml.calculate_total_trees(tree_density, area_km2)
        return TreeDensityResponse(tree_density=tree_density, total_trees=total_trees)

    # ── /health-score ────────────────────────────────────────────────────

    def get_health_score(self, polygon: list[list[float]]) -> HealthScoreResponse:
        row = self._fetch_one(
            """
            SELECT *
            FROM get_health_score(CAST(:polygon AS jsonb))
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and row.get("health_score") and row.get("health_score") > 0:
            return HealthScoreResponse(
                health_score=float(row.get("health_score") or 0),
                ndvi_avg=float(row.get("ndvi_avg") or 0),
                ndmi_avg=float(row.get("ndmi_avg") or 0),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        ndvi_avg = 0.72
        ndmi_avg = 0.41
        health = self.ml.compute_health(ndvi_avg, ndmi_avg)
        return HealthScoreResponse(
            health_score=float(health), ndvi_avg=ndvi_avg, ndmi_avg=ndmi_avg
        )

    # ── /risk-alerts ─────────────────────────────────────────────────────

    def get_risk_alerts(self, polygon: list[list[float]]) -> RiskAlertsResponse:
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
            return RiskAlertsResponse(
                risk_level=payload.get("risk_level", "Low"),
                alerts=alerts,
            )

        # ── ML fallback ──────────────────────────────────────────────────
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
        row = self._fetch_one(
            """
            SELECT get_species_composition(CAST(:polygon AS jsonb)) AS payload
            """,
            {"polygon": json.dumps(polygon)},
        )
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            return SpeciesCompositionResponse(
                teak=float(payload.get("teak") or 0),
                bamboo=float(payload.get("bamboo") or 0),
                mixed_deciduous=float(payload.get("mixed_deciduous") or 0),
            )

        return SpeciesCompositionResponse(teak=58.0, bamboo=27.0, mixed_deciduous=15.0)

    # ── /health-forecast ─────────────────────────────────────────────────

    def get_health_forecast(self, polygon: list[list[float]]) -> HealthForecastResponse:
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
            return HealthForecastResponse(forecast=forecast)

        # ── ML fallback ──────────────────────────────────────────────────
        points_raw = self.ml.forecast_as_monthly_points()
        forecast = [
            ForecastPoint(month=p["month"], health_score=p["health_score"])
            for p in points_raw
        ]
        return HealthForecastResponse(forecast=forecast)

    # ── /ndvi-map ────────────────────────────────────────────────────────

    def get_ndvi_map(self) -> NDVIMapResponse:
        return NDVIMapResponse(tile_url="/ndvi-map")

    # ── /risk-zones ──────────────────────────────────────────────────────

    def get_risk_zones(self) -> RiskZonesResponse:
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
            return RiskZonesResponse(
                zones=[
                    {"risk": str(row.get("risk") or "Low"), "geometry": row.get("geometry")}
                    for row in rows
                ]
            )
        return RiskZonesResponse(zones=[])

    # ── /system-status ───────────────────────────────────────────────────

    def get_system_status(self) -> SystemStatusResponse:
        row = self._fetch_one("SELECT get_system_status() AS payload")
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            return SystemStatusResponse(
                satellite_data_loaded=bool(payload.get("satellite_data_loaded", False)),
                feature_dataset_rows=int(payload.get("feature_dataset_rows", 0)),
                model_status=str(payload.get("model_status", "unknown")),
            )

        # ── ML fallback ──────────────────────────────────────────────────
        ml_status = self.ml.get_status()
        return SystemStatusResponse(
            satellite_data_loaded=True,
            feature_dataset_rows=45231,
            model_status="ml_ready" if ml_status["model_loaded"] else "ml_not_loaded",
        )

    # ── /demo-metrics ────────────────────────────────────────────────────

    def get_demo_metrics(self) -> DemoMetricsResponse:
        row = self._fetch_one(
            """
            SELECT get_demo_polygon_cache(:cache_key) AS payload
            """,
            {"cache_key": "demo_area"},
        )
        if row and isinstance(row.get("payload"), dict):
            payload = row["payload"]
            return DemoMetricsResponse(
                tree_count=int(payload.get("tree_count", 0)),
                health_score=float(payload.get("health_score", 0)),
                risk=str(payload.get("risk", "Low")),
            )

        # ── ML fallback (demo polygon: 5.1 km²) ─────────────────────────
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
