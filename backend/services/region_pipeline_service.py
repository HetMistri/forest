from __future__ import annotations

import hashlib
import json
import logging
import os
import calendar
from datetime import date, datetime, timezone
from time import perf_counter

from features.extractor import FeatureExtractor, FeatureExtractorConfig
from ingestion.downloader import (
    IngestionConfig,
    Sentinel1Downloader,
    Sentinel1IngestionConfig,
    Sentinel2Downloader,
)
from processing.preprocess import PreprocessConfig, Sentinel1Preprocessor, Sentinel2Preprocessor

logger = logging.getLogger(__name__)


class RegionPipelineService:
    _last_run_by_polygon: dict[str, datetime] = {}

    def __init__(self) -> None:
        self.enabled = os.getenv("REGION_PIPELINE_ENABLED", "true").lower() == "true"
        self.min_interval_seconds = int(os.getenv("REGION_PIPELINE_MIN_INTERVAL_SEC", "300"))

    def run_for_polygon(self, polygon: list[list[float]]) -> dict[str, object]:
        if not self.enabled:
            logger.info("Region pipeline skipped: disabled by REGION_PIPELINE_ENABLED")
            return {"enabled": False, "skipped": True}

        polygon_key = self._polygon_key(polygon)
        now = datetime.now(timezone.utc)
        last_run = self._last_run_by_polygon.get(polygon_key)
        if last_run is not None:
            elapsed = (now - last_run).total_seconds()
            if elapsed < self.min_interval_seconds:
                logger.info(
                    "Region pipeline skipped: recently processed polygon (elapsed=%.3fs, min_interval=%ss)",
                    elapsed,
                    self.min_interval_seconds,
                )
                return {
                    "enabled": True,
                    "skipped": True,
                    "reason": "recently_processed",
                    "elapsed_seconds": round(elapsed, 3),
                    "min_interval_seconds": self.min_interval_seconds,
                }

        self._last_run_by_polygon[polygon_key] = now

        end_date = now.date().isoformat()
        start_date = self._subtract_months(now.date(), int(os.getenv("INGESTION_LOOKBACK_MONTHS", "6"))).isoformat()

        run_id = self._build_run_id(polygon)
        logger.info(
            "Region pipeline started (run_id=%s, polygon_points=%d, lookback_start=%s, lookback_end=%s)",
            run_id,
            len(polygon),
            start_date,
            end_date,
        )
        pipeline_started = perf_counter()
        source_filename_s2 = f"sentinel2_{run_id}.tif"
        source_filename_s1 = f"sentinel1_{run_id}.tif"
        ndvi_filename = f"ndvi_{run_id}.tif"
        ndmi_filename = f"ndmi_{run_id}.tif"
        evi_filename = f"evi_{run_id}.tif"
        vv_filename = f"vv_{run_id}.tif"
        vh_filename = f"vh_{run_id}.tif"
        vv_vh_ratio_filename = f"vv_vh_ratio_{run_id}.tif"
        features_csv = f"features_{run_id}.csv"

        ingestion_started = perf_counter()
        ingestion_s2 = Sentinel2Downloader(
            IngestionConfig(
                start_date=start_date,
                end_date=end_date,
                region_polygon=polygon,
                output_name=source_filename_s2,
            )
        ).download_composite()
        logger.info(
            "Sentinel-2 ingestion completed (run_id=%s, output=%s, duration_ms=%.1f)",
            run_id,
            ingestion_s2,
            (perf_counter() - ingestion_started) * 1000,
        )

        ingestion_started = perf_counter()
        ingestion_s1 = Sentinel1Downloader(
            Sentinel1IngestionConfig(
                start_date=start_date,
                end_date=end_date,
                region_polygon=polygon,
                output_name=source_filename_s1,
            )
        ).download_composite()
        logger.info(
            "Sentinel-1 ingestion completed (run_id=%s, output=%s, duration_ms=%.1f)",
            run_id,
            ingestion_s1,
            (perf_counter() - ingestion_started) * 1000,
        )

        processing_started = perf_counter()
        processing_s2 = Sentinel2Preprocessor(
            PreprocessConfig(
                input_filename=source_filename_s2,
                ndvi_filename=ndvi_filename,
                ndmi_filename=ndmi_filename,
                evi_filename=evi_filename,
            )
        ).run()
        logger.info(
            "Sentinel-2 preprocessing completed (run_id=%s, outputs=%s, duration_ms=%.1f)",
            run_id,
            processing_s2,
            (perf_counter() - processing_started) * 1000,
        )

        processing_started = perf_counter()
        processing_s1 = Sentinel1Preprocessor(
            PreprocessConfig(
                sentinel1_input_filename=source_filename_s1,
                vv_filename=vv_filename,
                vh_filename=vh_filename,
                vv_vh_ratio_filename=vv_vh_ratio_filename,
            )
        ).run()
        logger.info(
            "Sentinel-1 preprocessing completed (run_id=%s, outputs=%s, duration_ms=%.1f)",
            run_id,
            processing_s1,
            (perf_counter() - processing_started) * 1000,
        )

        captured_at = datetime.now(timezone.utc)
        extraction_started = perf_counter()
        extraction = FeatureExtractor(
            FeatureExtractorConfig(
                ndvi_filename=ndvi_filename,
                ndmi_filename=ndmi_filename,
                evi_filename=evi_filename,
                vv_filename=vv_filename,
                vh_filename=vh_filename,
                vv_vh_ratio_filename=vv_vh_ratio_filename,
                output_csv=features_csv,
                source_name=f"sentinel-fusion:{run_id}",
                timestamp_utc=captured_at,
                write_to_db=True,
                grid_prefix=run_id,
            )
        ).run()
        logger.info(
            "Feature extraction completed (run_id=%s, rows_generated=%s, rows_inserted=%s, duration_ms=%.1f)",
            run_id,
            extraction.get("rows_generated"),
            extraction.get("rows_inserted"),
            (perf_counter() - extraction_started) * 1000,
        )
        logger.info(
            "Region pipeline completed (run_id=%s, total_duration_ms=%.1f)",
            run_id,
            (perf_counter() - pipeline_started) * 1000,
        )

        return {
            "enabled": True,
            "run_id": run_id,
            "start_date": start_date,
            "end_date": end_date,
            "ingestion": {
                "sentinel2": str(ingestion_s2),
                "sentinel1": str(ingestion_s1),
            },
            "processing": {
                "sentinel2": processing_s2,
                "sentinel1": processing_s1,
            },
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

    def _subtract_months(self, input_date: date, months: int) -> date:
        if months <= 0:
            return input_date

        month_index = input_date.month - months
        target_year = input_date.year + ((month_index - 1) // 12)
        target_month = ((month_index - 1) % 12) + 1
        last_day = calendar.monthrange(target_year, target_month)[1]
        target_day = min(input_date.day, last_day)
        return date(target_year, target_month, target_day)
