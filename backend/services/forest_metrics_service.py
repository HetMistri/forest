from __future__ import annotations

import csv
import json
import logging
import math
import os
from threading import Event, Lock, Thread
from datetime import datetime, timedelta, timezone
from hashlib import sha1
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from api.db import get_engine
from api.schemas import (
    DemoMetricsResponse,
    ForecastPoint,
    ForestMetricsResponse,
    HealthForecastResponse,
    HealthScoreResponse,
    NDVIMapResponse,
    PipelineStatusResponse,
    RiskAlert,
    RiskAlertsResponse,
    RiskZonesResponse,
    SpeciesCompositionResponse,
    SystemStatusResponse,
    TreeDensityResponse,
)
logger = logging.getLogger(__name__)


class ForestMetricsService:
    _pipeline_runs_in_progress: set[str] = set()
    _pipeline_completion_events: dict[str, Event] = {}
    _last_pipeline_result_by_polygon: dict[str, dict[str, Any]] = {}
    _pipeline_runs_lock = Lock()

    def __init__(self) -> None:
        from services.ml_bridge import MLBridge
        from services.region_pipeline_service import RegionPipelineService

        self.ml = MLBridge.get_instance()
        self.region_pipeline = RegionPipelineService()
        self.strict_prod_mode = os.getenv("STRICT_PROD_MODE", "true").lower() == "true"
        self.demo_cache_enabled = os.getenv("DEMO_CACHE_ENABLED", "false").lower() == "true"
        self.trigger_pipeline_on_request = (
            os.getenv("REGION_PIPELINE_TRIGGER_ON_REQUEST", "true").lower() == "true"
        )
        self.pipeline_async = os.getenv("REGION_PIPELINE_ASYNC", "true").lower() == "true"
        self.pipeline_wait_for_completion = (
            os.getenv("REGION_PIPELINE_WAIT_FOR_COMPLETION", "false").lower() == "true"
        )

    def _strict_unavailable(self, endpoint: str, detail: str) -> None:
        logger.error("%s unavailable in strict mode: %s", endpoint, detail)
        raise HTTPException(status_code=503, detail=detail)

    def _pipeline_worker(self, polygon: list[list[float]], polygon_fp: str) -> None:
        try:
            logger.info("Region pipeline background run started (polygon=%s)", polygon_fp)
            result = self.region_pipeline.run_for_polygon(polygon)
            logger.info("Region pipeline background run finished (polygon=%s): %s", polygon_fp, result)
            with self._pipeline_runs_lock:
                self._last_pipeline_result_by_polygon[polygon_fp] = result
        except Exception as exc:
            logger.warning("Region pipeline background run failed (polygon=%s): %s", polygon_fp, exc)
            with self._pipeline_runs_lock:
                self._last_pipeline_result_by_polygon[polygon_fp] = {
                    "enabled": True,
                    "error": str(exc),
                }
        finally:
            with self._pipeline_runs_lock:
                self._pipeline_runs_in_progress.discard(polygon_fp)
                event = self._pipeline_completion_events.pop(polygon_fp, None)

            if event is not None:
                event.set()

    def _launch_pipeline_background(self, polygon: list[list[float]], polygon_fp: str) -> Event:
        should_start_thread = False
        with self._pipeline_runs_lock:
            event = self._pipeline_completion_events.get(polygon_fp)
            if event is None:
                event = Event()
                self._pipeline_completion_events[polygon_fp] = event

            if polygon_fp in self._pipeline_runs_in_progress:
                logger.info("Region pipeline already in progress; skipping duplicate trigger (polygon=%s)", polygon_fp)
                return event

            event.clear()
            self._pipeline_runs_in_progress.add(polygon_fp)
            should_start_thread = True

        if not should_start_thread:
            return event

        thread = Thread(
            target=self._pipeline_worker,
            args=(polygon, polygon_fp),
            name=f"region-pipeline-{polygon_fp}",
            daemon=True,
        )
        thread.start()
        logger.info("Region pipeline launched in background (polygon=%s, thread=%s)", polygon_fp, thread.name)
        return event

    def _wait_for_pipeline_completion(self, polygon_fp: str) -> None:
        with self._pipeline_runs_lock:
            event = self._pipeline_completion_events.get(polygon_fp)
            in_progress = polygon_fp in self._pipeline_runs_in_progress

        if not in_progress or event is None:
            return

        logger.info("Waiting for region pipeline completion (polygon=%s)", polygon_fp)
        event.wait()
        logger.info("Region pipeline completion wait finished (polygon=%s)", polygon_fp)

    def _prepare_region_data(self, polygon: list[list[float]]) -> None:
        if not self.trigger_pipeline_on_request:
            return

        polygon_fp = self._polygon_fingerprint(polygon)
        try:
            if self.pipeline_async:
                logger.info("Region pipeline trigger enabled; launching async run for polygon=%s", polygon_fp)
                self._launch_pipeline_background(polygon, polygon_fp)
                if self.pipeline_wait_for_completion:
                    self._wait_for_pipeline_completion(polygon_fp)
                return

            logger.info("Region pipeline trigger enabled; running synchronously for polygon=%s", polygon_fp)
            result = self.region_pipeline.run_for_polygon(polygon)
            logger.info("Region pipeline run result (polygon=%s): %s", polygon_fp, result)
            with self._pipeline_runs_lock:
                self._last_pipeline_result_by_polygon[polygon_fp] = result
        except Exception as exc:
            logger.warning("Region pipeline failed for polygon request: %s", exc)

    def _safe_float(self, value: Any, default: float | None = None) -> float | None:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _metrics_from_summary(
        self,
        *,
        ndvi_avg: float,
        ndmi_avg: float,
        vv_avg: float,
        vh_avg: float,
        vv_vh_ratio_avg: float,
        ndvi_trend_avg: float,
        area_km2: float,
        centroid_lon: float,
        centroid_lat: float,
    ) -> dict[str, Any]:
        tree_density = self.ml.predict_density(
            ndvi=ndvi_avg,
            ndmi=ndmi_avg,
            vv=vv_avg,
            vh=vh_avg,
            sar_ratio=vv_vh_ratio_avg,
        )
        tree_count = self.ml.calculate_total_trees(tree_density, area_km2)
        health_score = float(self.ml.compute_health(ndvi_avg, ndmi_avg))

        if ndvi_trend_avg <= -0.08 or health_score < 40:
            risk_level = "High"
        elif ndvi_trend_avg <= -0.03 or health_score < 70:
            risk_level = "Moderate"
        else:
            risk_level = "Low"

        teak = self._clamp(44.0 + (ndvi_avg * 32.0) + (ndmi_avg * 6.0), 10.0, 82.0)
        bamboo = self._clamp(30.0 + (ndmi_avg * 24.0) - (ndvi_avg * 8.0), 8.0, 75.0)
        mixed_deciduous = self._clamp(100.0 - teak - bamboo, 5.0, 85.0)
        total = teak + bamboo + mixed_deciduous
        species_distribution = {
            "teak": round((teak / total) * 100.0, 2),
            "bamboo": round((bamboo / total) * 100.0, 2),
            "mixed_deciduous": round((mixed_deciduous / total) * 100.0, 2),
        }

        trend_impact = self._clamp(ndvi_trend_avg * 120.0, -6.0, 6.0)
        forecast_points: list[dict[str, Any]] = []
        base_dt = datetime.now(timezone.utc)
        for i in range(1, 7):
            projected = self._clamp(health_score + (trend_impact * i), 0.0, 100.0)
            forecast_points.append(
                {
                    "month": (base_dt + timedelta(days=30 * i)).strftime("%Y-%m"),
                    "health_score": round(projected, 2),
                }
            )

        return {
            "area_km2": area_km2,
            "tree_density": tree_density,
            "tree_count": tree_count,
            "health_score": health_score,
            "risk_level": risk_level,
            "species_distribution": species_distribution,
            "forecast_health": float(forecast_points[0]["health_score"]),
            "forecast_points": forecast_points,
            "ndvi_avg": ndvi_avg,
            "ndmi_avg": ndmi_avg,
            "centroid_lon": centroid_lon,
            "centroid_lat": centroid_lat,
        }

    def _derive_metrics_from_pipeline_artifacts(
        self,
        polygon: list[list[float]],
        polygon_fp: str,
    ) -> dict[str, Any] | None:
        with self._pipeline_runs_lock:
            result = self._last_pipeline_result_by_polygon.get(polygon_fp)

        if not isinstance(result, dict):
            return None

        extraction = result.get("extraction")
        if not isinstance(extraction, dict):
            return None

        csv_path_raw = extraction.get("features_csv")
        if not isinstance(csv_path_raw, str) or not csv_path_raw:
            return None

        ndvi_values: list[float] = []
        ndmi_values: list[float] = []
        vv_values: list[float] = []
        vh_values: list[float] = []
        ratio_values: list[float] = []
        trend_values: list[float] = []
        lon_values: list[float] = []
        lat_values: list[float] = []

        try:
            with open(csv_path_raw, "r", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    ndvi = self._safe_float(row.get("ndvi"))
                    ndmi = self._safe_float(row.get("ndmi"))
                    vv = self._safe_float(row.get("vv"), -7.5)
                    vh = self._safe_float(row.get("vh"), -14.2)
                    ratio = self._safe_float(row.get("vv_vh_ratio"), 0.52)
                    trend = self._safe_float(row.get("ndvi_trend"), 0.0)
                    lon = self._safe_float(row.get("lon"))
                    lat = self._safe_float(row.get("lat"))

                    if ndvi is None or ndmi is None:
                        continue

                    ndvi_values.append(ndvi)
                    ndmi_values.append(ndmi)
                    vv_values.append(vv if vv is not None else -7.5)
                    vh_values.append(vh if vh is not None else -14.2)
                    ratio_values.append(ratio if ratio is not None else 0.52)
                    trend_values.append(trend if trend is not None else 0.0)
                    if lon is not None:
                        lon_values.append(lon)
                    if lat is not None:
                        lat_values.append(lat)
        except Exception as exc:
            logger.warning("Failed reading pipeline extracted features CSV (polygon=%s, path=%s): %s", polygon_fp, csv_path_raw, exc)
            return None

        if not ndvi_values:
            return None

        ndvi_avg = sum(ndvi_values) / len(ndvi_values)
        ndmi_avg = sum(ndmi_values) / len(ndmi_values)
        vv_avg = sum(vv_values) / len(vv_values) if vv_values else -7.5
        vh_avg = sum(vh_values) / len(vh_values) if vh_values else -14.2
        vv_vh_ratio_avg = sum(ratio_values) / len(ratio_values) if ratio_values else 0.52
        ndvi_trend_avg = sum(trend_values) / len(trend_values) if trend_values else 0.0
        centroid_lon = sum(lon_values) / len(lon_values) if lon_values else 0.0
        centroid_lat = sum(lat_values) / len(lat_values) if lat_values else 0.0

        metrics = self._metrics_from_summary(
            ndvi_avg=ndvi_avg,
            ndmi_avg=ndmi_avg,
            vv_avg=vv_avg,
            vh_avg=vh_avg,
            vv_vh_ratio_avg=vv_vh_ratio_avg,
            ndvi_trend_avg=ndvi_trend_avg,
            area_km2=self._area_km2(polygon),
            centroid_lon=centroid_lon,
            centroid_lat=centroid_lat,
        )
        logger.info(
            "Metrics derived from pipeline extracted artifacts (polygon=%s, samples=%d, path=%s)",
            polygon_fp,
            len(ndvi_values),
            csv_path_raw,
        )
        return metrics

    def _polygon_fingerprint(self, polygon: list[list[float]]) -> str:
        canonical = json.dumps(polygon, separators=(",", ":"), ensure_ascii=False)
        return sha1(canonical.encode("utf-8")).hexdigest()[:10]

    def _pipeline_state(self, polygon_fp: str) -> tuple[bool, str | None]:
        with self._pipeline_runs_lock:
            in_progress = polygon_fp in self._pipeline_runs_in_progress
            last_result = self._last_pipeline_result_by_polygon.get(polygon_fp)

        if isinstance(last_result, dict):
            raw_error = last_result.get("error")
            if isinstance(raw_error, str) and raw_error.strip():
                return in_progress, raw_error.strip()

        return in_progress, None

    def _is_no_data_pipeline_error(self, error_message: str | None) -> bool:
        if not error_message:
            return False
        text = error_message.lower()
        return (
            "no bands" in text
            or "image with no bands" in text
            or "no image" in text
            or "no valid pixels" in text
            or "empty collection" in text
        )

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
        """
        Estimate polygon area in square-kilometers from [lon, lat] coordinates.

        Uses a spherical polygon area approximation (WGS84 mean Earth radius),
        which is stable for both small and very large regions.
        """
        if len(polygon) < 3:
            return 0.0

        ring = [(float(point[0]), float(point[1])) for point in polygon if len(point) >= 2]
        if len(ring) < 3:
            return 0.0

        if ring[0] != ring[-1]:
            ring.append(ring[0])

        earth_radius_m = 6_371_008.8
        area_accumulator = 0.0

        for index in range(len(ring) - 1):
            lon1_deg, lat1_deg = ring[index]
            lon2_deg, lat2_deg = ring[index + 1]

            lat1 = math.radians(lat1_deg)
            lat2 = math.radians(lat2_deg)
            lon1 = math.radians(lon1_deg)
            lon2 = math.radians(lon2_deg)

            delta_lon = lon2 - lon1
            if delta_lon > math.pi:
                delta_lon -= 2 * math.pi
            elif delta_lon < -math.pi:
                delta_lon += 2 * math.pi

            area_accumulator += delta_lon * (math.sin(lat1) + math.sin(lat2))

        area_m2 = abs(area_accumulator) * (earth_radius_m**2) / 2.0
        area_km2 = area_m2 / 1_000_000.0
        return round(area_km2, 2)

    def _clamp(self, value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _feature_summary(self, polygon: list[list[float]]) -> dict[str, Any] | None:
        row = self._fetch_one(
            """
            WITH poly AS (
                SELECT json_polygon_to_geom(CAST(:polygon AS jsonb)) AS geom
            )
            SELECT
                COUNT(*)::int AS sample_count,
                COALESCE(AVG(ff.ndvi), 0) AS ndvi_avg,
                COALESCE(AVG(ff.ndmi), 0) AS ndmi_avg,
                COALESCE(AVG(ff.vv), -7.5) AS vv_avg,
                COALESCE(AVG(ff.vh), -14.2) AS vh_avg,
                COALESCE(AVG(ff.vv_vh_ratio), 0.52) AS vv_vh_ratio_avg,
                COALESCE(AVG(ff.ndvi_trend), 0) AS ndvi_trend_avg,
                COALESCE(ST_X(ST_Centroid(ST_Collect(ff.geometry))), 0) AS centroid_lon,
                COALESCE(ST_Y(ST_Centroid(ST_Collect(ff.geometry))), 0) AS centroid_lat
            FROM forest_features ff
            CROSS JOIN poly
            WHERE ST_Intersects(ff.geometry, poly.geom)
            """,
            {"polygon": json.dumps(polygon)},
        )
        if not row or int(row.get("sample_count") or 0) <= 0:
            return None
        return row

    def _has_feature_data(self, polygon: list[list[float]]) -> bool:
        row = self._fetch_one(
            """
            WITH poly AS (
                SELECT json_polygon_to_geom(CAST(:polygon AS jsonb)) AS geom
            )
            SELECT EXISTS(
                SELECT 1
                FROM forest_features ff
                CROSS JOIN poly
                WHERE ST_Intersects(ff.geometry, poly.geom)
                LIMIT 1
            ) AS has_data
            """,
            {"polygon": json.dumps(polygon)},
        )
        if not row:
            return False
        return bool(row.get("has_data", False))

    def get_pipeline_status(self, polygon: list[list[float]]) -> PipelineStatusResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        in_progress, pipeline_error = self._pipeline_state(polygon_fp)

        has_feature_data = self._has_feature_data(polygon)
        if not has_feature_data:
            has_feature_data = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp) is not None
        if not has_feature_data and self.demo_cache_enabled:
            has_feature_data = self._get_demo_cached_forest_metrics(polygon) is not None

        if has_feature_data:
            status = "ready"
            detail = "Feature data is available for this polygon."
            if in_progress:
                detail = "Feature data is available; background refresh is in progress."
        elif in_progress:
            status = "processing"
            detail = "Region pipeline is running for this polygon."
        elif self._is_no_data_pipeline_error(pipeline_error):
            status = "unavailable"
            detail = "No satellite data found for this area/time window. Try another region or date range."
        else:
            status = "unavailable"
            detail = "No feature data found and no active pipeline run for this polygon."

        logger.info(
            "Pipeline status served (polygon=%s, status=%s, in_progress=%s, has_feature_data=%s)",
            polygon_fp,
            status,
            in_progress,
            has_feature_data,
        )
        return PipelineStatusResponse(
            status=status,
            in_progress=in_progress,
            has_feature_data=has_feature_data,
            detail=detail,
        )

    def _derive_live_metrics_from_features(self, polygon: list[list[float]]) -> dict[str, Any] | None:
        summary = self._feature_summary(polygon)
        if summary is None:
            return None

        ndvi_avg = float(summary.get("ndvi_avg") or 0)
        ndmi_avg = float(summary.get("ndmi_avg") or 0)
        vv_avg = float(summary.get("vv_avg") or -7.5)
        vh_avg = float(summary.get("vh_avg") or -14.2)
        vv_vh_ratio_avg = float(summary.get("vv_vh_ratio_avg") or 0.52)
        ndvi_trend_avg = float(summary.get("ndvi_trend_avg") or 0)
        area_km2 = self._area_km2(polygon)
        return self._metrics_from_summary(
            ndvi_avg=ndvi_avg,
            ndmi_avg=ndmi_avg,
            vv_avg=vv_avg,
            vh_avg=vh_avg,
            vv_vh_ratio_avg=vv_vh_ratio_avg,
            ndvi_trend_avg=ndvi_trend_avg,
            area_km2=area_km2,
            centroid_lon=float(summary.get("centroid_lon") or 0),
            centroid_lat=float(summary.get("centroid_lat") or 0),
        )

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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            logger.info("Forest metrics served from feature-derived live computation (polygon=%s)", polygon_fp)
            return ForestMetricsResponse(
                area_km2=float(derived["area_km2"]),
                tree_count=int(derived["tree_count"]),
                tree_density=float(derived["tree_density"]),
                health_score=float(derived["health_score"]),
                risk_level=str(derived["risk_level"]),
                species_distribution=dict(derived["species_distribution"]),
                forecast_health=float(derived["forecast_health"]),
            )

        if self.trigger_pipeline_on_request:
            in_progress, pipeline_error = self._pipeline_state(polygon_fp)
            if in_progress:
                raise HTTPException(
                    status_code=503,
                    detail="Pipeline processing for selected polygon. Please retry shortly.",
                )
            if self._is_no_data_pipeline_error(pipeline_error):
                raise HTTPException(
                    status_code=422,
                    detail="No satellite data found for selected area/time window. Try another region or date range.",
                )

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/forest-metrics",
                "No real metrics available for selected polygon. Ensure pipeline ingestion/extraction completed and DB functions are populated.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Forest metrics unavailable after pipeline attempt (polygon=%s); falling back to ML bridge",
                polygon_fp,
            )

        # Legacy fallback mode (non-strict)
        logger.warning("Forest metrics fallback to ML bridge (polygon=%s)", polygon_fp)
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        tree_count = self.ml.calculate_total_trees(tree_density, area_km2)
        health_score = float(self.ml.compute_health())
        risk_raw = self.ml.detect_risk()
        risk_level = self.ml.classify_risk_level(risk_raw)
        forecast_points = self.ml.forecast_as_monthly_points()
        forecast_health = float(forecast_points[0]["health_score"]) if forecast_points else health_score

        return ForestMetricsResponse(
            area_km2=area_km2,
            tree_count=tree_count,
            tree_density=tree_density,
            health_score=health_score,
            risk_level=risk_level,
            species_distribution={"teak": 58.0, "bamboo": 27.0, "mixed_deciduous": 15.0},
            forecast_health=forecast_health,
        )

    # ── /tree-density ────────────────────────────────────────────────────

    def get_tree_density(self, polygon: list[list[float]]) -> TreeDensityResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Tree density requested (polygon=%s, points=%d)", polygon_fp, len(polygon))

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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            logger.info("Tree density served from feature-derived live computation (polygon=%s)", polygon_fp)
            return TreeDensityResponse(
                tree_density=float(derived["tree_density"]),
                total_trees=int(derived["tree_count"]),
            )

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/tree-density",
                "No real tree density available for selected polygon. Run pipeline and verify forest feature tables are populated.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Tree density unavailable after pipeline attempt (polygon=%s); falling back to ML bridge",
                polygon_fp,
            )

        # Legacy fallback mode (non-strict)
        logger.warning("Tree density fallback to ML bridge (polygon=%s)", polygon_fp)
        area_km2 = self._area_km2(polygon)
        tree_density = self.ml.predict_density()
        total_trees = self.ml.calculate_total_trees(tree_density, area_km2)
        return TreeDensityResponse(tree_density=tree_density, total_trees=total_trees)

    # ── /health-score ────────────────────────────────────────────────────

    def get_health_score(self, polygon: list[list[float]]) -> HealthScoreResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Health score requested (polygon=%s, points=%d)", polygon_fp, len(polygon))

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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            logger.info("Health score served from feature-derived live computation (polygon=%s)", polygon_fp)
            return HealthScoreResponse(
                health_score=float(derived["health_score"]),
                ndvi_avg=float(derived["ndvi_avg"]),
                ndmi_avg=float(derived["ndmi_avg"]),
            )

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/health-score",
                "No real health score available for selected polygon. Run pipeline and verify NDVI/NDMI aggregation is available.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Health score unavailable after pipeline attempt (polygon=%s); falling back to ML bridge",
                polygon_fp,
            )

        # Legacy fallback mode (non-strict)
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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            logger.info("Risk alerts served from feature-derived live computation (polygon=%s)", polygon_fp)
            risk_level = str(derived["risk_level"])
            alerts: list[RiskAlert] = []
            if risk_level != "Low":
                alerts.append(
                    RiskAlert(
                        type="NDVI_TREND",
                        severity=risk_level,
                        location=[
                            float(derived["centroid_lat"]),
                            float(derived["centroid_lon"]),
                        ],
                    )
                )
            return RiskAlertsResponse(risk_level=risk_level, alerts=alerts)

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/risk-alerts",
                "No real risk alerts available for selected polygon. Run pipeline and verify risk alert generation data is available.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Risk alerts unavailable after pipeline attempt (polygon=%s); falling back to ML bridge",
                polygon_fp,
            )

        # Legacy fallback mode (non-strict)
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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            species_distribution = dict(derived["species_distribution"])
            logger.info("Species composition served from feature-derived live computation (polygon=%s)", polygon_fp)
            return SpeciesCompositionResponse(
                teak=float(species_distribution.get("teak") or 0),
                bamboo=float(species_distribution.get("bamboo") or 0),
                mixed_deciduous=float(species_distribution.get("mixed_deciduous") or 0),
            )

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/species-composition",
                "No real species composition available for selected polygon. Run pipeline and verify species composition source data.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Species composition unavailable after pipeline attempt (polygon=%s); using static fallback",
                polygon_fp,
            )

        logger.warning("Species composition using static fallback values (polygon=%s)", polygon_fp)
        return SpeciesCompositionResponse(teak=58.0, bamboo=27.0, mixed_deciduous=15.0)

    # ── /health-forecast ─────────────────────────────────────────────────

    def get_health_forecast(self, polygon: list[list[float]]) -> HealthForecastResponse:
        polygon_fp = self._polygon_fingerprint(polygon)
        logger.info("Health forecast requested (polygon=%s, points=%d)", polygon_fp, len(polygon))

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

        derived = self._derive_live_metrics_from_features(polygon)
        if derived is None:
            derived = self._derive_metrics_from_pipeline_artifacts(polygon, polygon_fp)
        if derived is not None:
            logger.info("Health forecast served from feature-derived live computation (polygon=%s)", polygon_fp)
            forecast = [
                ForecastPoint(month=str(item["month"]), health_score=float(item["health_score"]))
                for item in derived["forecast_points"]
            ]
            return HealthForecastResponse(forecast=forecast)

        if self.strict_prod_mode and not self.trigger_pipeline_on_request:
            self._strict_unavailable(
                "/health-forecast",
                "No real health forecast available for selected polygon. Run pipeline and verify historical series is available.",
            )
        elif self.strict_prod_mode:
            logger.warning(
                "Health forecast unavailable after pipeline attempt (polygon=%s); falling back to ML bridge",
                polygon_fp,
            )

        # Legacy fallback mode (non-strict)
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

        ml_status = self.ml.get_status()
        logger.warning("System status derived from ML/DB availability status: %s", ml_status)
        return SystemStatusResponse(
            satellite_data_loaded=False,
            feature_dataset_rows=0,
            model_status="ml_ready" if ml_status.get("model_loaded") else "ml_not_loaded",
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

        if self.strict_prod_mode:
            self._strict_unavailable(
                "/demo-metrics",
                "Demo endpoint has no cached real data. Demo/static fallbacks are disabled in strict mode.",
            )

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
