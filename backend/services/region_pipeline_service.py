from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from features.extractor import FeatureExtractor, FeatureExtractorConfig
from ingestion.downloader import IngestionConfig, Sentinel2Downloader
from processing.preprocess import PreprocessConfig, Sentinel2Preprocessor


class RegionPipelineService:
    _last_run_by_polygon: dict[str, datetime] = {}

    def __init__(self) -> None:
        self.enabled = os.getenv("REGION_PIPELINE_ENABLED", "true").lower() == "true"
        self.min_interval_seconds = int(os.getenv("REGION_PIPELINE_MIN_INTERVAL_SEC", "300"))

    def run_for_polygon(self, polygon: list[list[float]]) -> dict[str, object]:
        if not self.enabled:
            return {"enabled": False, "skipped": True}

        polygon_key = self._polygon_key(polygon)
        now = datetime.now(timezone.utc)
        last_run = self._last_run_by_polygon.get(polygon_key)
        if last_run is not None:
            elapsed = (now - last_run).total_seconds()
            if elapsed < self.min_interval_seconds:
                return {
                    "enabled": True,
                    "skipped": True,
                    "reason": "recently_processed",
                    "elapsed_seconds": round(elapsed, 3),
                    "min_interval_seconds": self.min_interval_seconds,
                }

        self._last_run_by_polygon[polygon_key] = now

        run_id = self._build_run_id(polygon)
        source_filename = f"sentinel2_{run_id}.tif"
        ndvi_filename = f"ndvi_{run_id}.tif"
        ndmi_filename = f"ndmi_{run_id}.tif"
        features_csv = f"features_{run_id}.csv"

        ingestion = Sentinel2Downloader(
            IngestionConfig(
                region_polygon=polygon,
                output_name=source_filename,
            )
        ).download_composite()

        processing = Sentinel2Preprocessor(
            PreprocessConfig(
                input_filename=source_filename,
                ndvi_filename=ndvi_filename,
                ndmi_filename=ndmi_filename,
            )
        ).run()

        captured_at = datetime.now(timezone.utc)
        extraction = FeatureExtractor(
            FeatureExtractorConfig(
                ndvi_filename=ndvi_filename,
                ndmi_filename=ndmi_filename,
                output_csv=features_csv,
                source_name=f"sentinel2:{run_id}",
                timestamp_utc=captured_at,
                write_to_db=True,
                grid_prefix=run_id,
            )
        ).run()

        return {
            "enabled": True,
            "run_id": run_id,
            "ingestion_output": str(ingestion),
            "processing": processing,
            "extraction": extraction,
        }

    def _build_run_id(self, polygon: list[list[float]]) -> str:
        canonical = self._polygon_key(polygon)
        digest = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:10]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"reg_{ts}_{digest}"

    def _polygon_key(self, polygon: list[list[float]]) -> str:
        rounded = [[round(point[0], 6), round(point[1], 6)] for point in polygon]
        return json.dumps(rounded, separators=(",", ":"), sort_keys=False)
