from __future__ import annotations

import argparse
import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from database.db import FeatureRecord, PostgresFeatureStore


@dataclass(slots=True)
class FeatureExtractorConfig:
    processed_data_dir: Path = field(default_factory=lambda: _resolve_data_dir("PROCESSED_DATA_DIR", "processed"))
    ndvi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDVI_NAME", "ndvi.tif"))
    ndmi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDMI_NAME", "ndmi.tif"))
    evi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_EVI_NAME", "evi.tif"))
    vv_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_VV_NAME", "vv.tif"))
    vh_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_VH_NAME", "vh.tif"))
    vv_vh_ratio_filename: str = field(
        default_factory=lambda: os.getenv("PROCESSING_VV_VH_RATIO_NAME", "vv_vh_ratio.tif")
    )
    ndvi_baseline_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDVI_BASELINE_NAME", ""))
    output_csv: str = field(default_factory=lambda: os.getenv("FEATURES_OUTPUT_CSV", "features.csv"))
    source_name: str = field(default_factory=lambda: os.getenv("FEATURES_SOURCE_NAME", "sentinel2"))
    timestamp_utc: datetime = field(default_factory=lambda: _resolve_timestamp(os.getenv("FEATURES_TIMESTAMP_UTC")))
    write_to_db: bool = field(default_factory=lambda: os.getenv("FEATURES_WRITE_TO_DB", "true").lower() == "true")
    skip_nodata: bool = field(default_factory=lambda: os.getenv("FEATURES_SKIP_NODATA", "true").lower() == "true")
    grid_prefix: str = field(default_factory=lambda: os.getenv("FEATURES_GRID_PREFIX", "cell"))


class FeatureExtractor:
    def __init__(self, config: FeatureExtractorConfig | None = None) -> None:
        self.config = config or FeatureExtractorConfig()

    def run(self) -> dict[str, object]:
        rasterio = _import_rasterio()

        ndvi_path = self.config.processed_data_dir / self.config.ndvi_filename
        ndmi_path = self.config.processed_data_dir / self.config.ndmi_filename
        evi_path = self.config.processed_data_dir / self.config.evi_filename
        vv_path = self.config.processed_data_dir / self.config.vv_filename
        vh_path = self.config.processed_data_dir / self.config.vh_filename
        ratio_path = self.config.processed_data_dir / self.config.vv_vh_ratio_filename
        ndvi_baseline_path = (
            self.config.processed_data_dir / self.config.ndvi_baseline_filename
            if self.config.ndvi_baseline_filename
            else None
        )
        if not ndvi_path.exists():
            raise FileNotFoundError(f"NDVI raster not found: {ndvi_path}")
        if not ndmi_path.exists():
            raise FileNotFoundError(f"NDMI raster not found: {ndmi_path}")

        evi_available = evi_path.exists()
        vv_available = vv_path.exists()
        vh_available = vh_path.exists()
        ratio_available = ratio_path.exists()
        ndvi_baseline_available = ndvi_baseline_path is not None and ndvi_baseline_path.exists()

        output_csv_path = self.config.processed_data_dir / self.config.output_csv
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)

        with rasterio.open(ndvi_path) as ndvi_src, rasterio.open(ndmi_path) as ndmi_src:
            if (
                ndvi_src.width != ndmi_src.width
                or ndvi_src.height != ndmi_src.height
                or ndvi_src.transform != ndmi_src.transform
                or ndvi_src.crs != ndmi_src.crs
            ):
                raise ValueError("NDVI and NDMI rasters must share the same grid, transform, and CRS")

            ndvi_data = ndvi_src.read(1)
            ndmi_data = ndmi_src.read(1)
            evi_data = self._read_optional_band(rasterio, evi_path, ndvi_src, evi_available)
            vv_data = self._read_optional_band(rasterio, vv_path, ndvi_src, vv_available)
            vh_data = self._read_optional_band(rasterio, vh_path, ndvi_src, vh_available)
            ratio_data = self._read_optional_band(rasterio, ratio_path, ndvi_src, ratio_available)
            ndvi_baseline_data = self._read_optional_band(
                rasterio,
                ndvi_baseline_path,
                ndvi_src,
                ndvi_baseline_available,
            )

            rows, db_records = self._build_rows(
                ndvi_data=ndvi_data,
                ndmi_data=ndmi_data,
                evi_data=evi_data,
                vv_data=vv_data,
                vh_data=vh_data,
                ratio_data=ratio_data,
                ndvi_baseline_data=ndvi_baseline_data,
                transform=ndvi_src.transform,
                nodata_ndvi=ndvi_src.nodata,
                nodata_ndmi=ndmi_src.nodata,
            )

        self._write_csv(output_csv_path, rows)

        inserted = 0
        if self.config.write_to_db and db_records:
            store = PostgresFeatureStore()
            inserted = store.upsert_forest_features(db_records)

        metadata = {
            "ndvi_path": str(ndvi_path),
            "ndmi_path": str(ndmi_path),
            "evi_path": str(evi_path) if evi_available else None,
            "vv_path": str(vv_path) if vv_available else None,
            "vh_path": str(vh_path) if vh_available else None,
            "vv_vh_ratio_path": str(ratio_path) if ratio_available else None,
            "ndvi_baseline_path": str(ndvi_baseline_path) if ndvi_baseline_available else None,
            "output_csv": str(output_csv_path),
            "rows_generated": len(rows),
            "rows_inserted": inserted,
            "write_to_db": self.config.write_to_db,
            "timestamp_utc": self.config.timestamp_utc.isoformat(),
            "source_name": self.config.source_name,
        }
        metadata_path = output_csv_path.with_suffix(".metadata.json")
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "features_csv": str(output_csv_path),
            "metadata": str(metadata_path),
            "rows_generated": len(rows),
            "rows_inserted": inserted,
        }

    def _build_rows(
        self,
        ndvi_data: np.ndarray,
        ndmi_data: np.ndarray,
        evi_data: np.ndarray | None,
        vv_data: np.ndarray | None,
        vh_data: np.ndarray | None,
        ratio_data: np.ndarray | None,
        ndvi_baseline_data: np.ndarray | None,
        transform,
        nodata_ndvi: float | None,
        nodata_ndmi: float | None,
    ) -> tuple[list[dict[str, object]], list[FeatureRecord]]:
        rows: list[dict[str, object]] = []
        records: list[FeatureRecord] = []

        height, width = ndvi_data.shape
        for row_idx in range(height):
            for col_idx in range(width):
                ndvi_val = float(ndvi_data[row_idx, col_idx])
                ndmi_val = float(ndmi_data[row_idx, col_idx])
                evi_val = self._optional_value(evi_data, row_idx, col_idx)
                vv_val = self._optional_value(vv_data, row_idx, col_idx)
                vh_val = self._optional_value(vh_data, row_idx, col_idx)
                vv_vh_ratio_val = self._optional_value(ratio_data, row_idx, col_idx)
                ndvi_baseline_val = self._optional_value(ndvi_baseline_data, row_idx, col_idx)
                ndvi_trend_val = (
                    ndvi_val - ndvi_baseline_val if ndvi_baseline_val is not None else 0.0
                )

                if self._should_skip(ndvi_val, ndmi_val, nodata_ndvi, nodata_ndmi):
                    continue

                min_lon, min_lat, max_lon, max_lat, centroid_lon, centroid_lat = _cell_geometry_bounds(
                    transform,
                    row_idx,
                    col_idx,
                )
                grid_id = _grid_id(self.config.grid_prefix, row_idx, col_idx)

                rows.append(
                    {
                        "grid_id": grid_id,
                        "lat": centroid_lat,
                        "lon": centroid_lon,
                        "ndvi": round(ndvi_val, 6),
                        "ndmi": round(ndmi_val, 6),
                        "evi": self._round_optional(evi_val),
                        "vv": self._round_optional(vv_val),
                        "vh": self._round_optional(vh_val),
                        "vv_vh_ratio": self._round_optional(vv_vh_ratio_val),
                        "ndvi_trend": round(float(ndvi_trend_val), 6),
                        "timestamp": self.config.timestamp_utc.isoformat(),
                    }
                )

                records.append(
                    FeatureRecord(
                        grid_id=grid_id,
                        min_lon=min_lon,
                        min_lat=min_lat,
                        max_lon=max_lon,
                        max_lat=max_lat,
                        ndvi=ndvi_val,
                        ndmi=ndmi_val,
                        evi=evi_val,
                        vv=vv_val,
                        vh=vh_val,
                        vv_vh_ratio=vv_vh_ratio_val,
                        ndvi_trend=float(ndvi_trend_val),
                        source=self.config.source_name,
                        captured_at=self.config.timestamp_utc,
                    )
                )

        return rows, records

    def _should_skip(
        self,
        ndvi_val: float,
        ndmi_val: float,
        nodata_ndvi: float | None,
        nodata_ndmi: float | None,
    ) -> bool:
        if not np.isfinite(ndvi_val) or not np.isfinite(ndmi_val):
            return True

        if not self.config.skip_nodata:
            return False

        ndvi_is_nodata = nodata_ndvi is not None and ndvi_val == nodata_ndvi
        ndmi_is_nodata = nodata_ndmi is not None and ndmi_val == nodata_ndmi
        return ndvi_is_nodata or ndmi_is_nodata

    def _write_csv(self, output_path: Path, rows: list[dict[str, object]]) -> None:
        fieldnames = [
            "grid_id",
            "lat",
            "lon",
            "ndvi",
            "ndmi",
            "evi",
            "vv",
            "vh",
            "vv_vh_ratio",
            "ndvi_trend",
            "timestamp",
        ]
        with output_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    def _read_optional_band(self, rasterio, raster_path: Path | None, reference_src, enabled: bool) -> np.ndarray | None:
        if not enabled or raster_path is None:
            return None

        with rasterio.open(raster_path) as src:
            if (
                src.width != reference_src.width
                or src.height != reference_src.height
                or src.transform != reference_src.transform
                or src.crs != reference_src.crs
            ):
                raise ValueError(f"Raster {raster_path.name} does not align with NDVI grid")
            return src.read(1)

    def _optional_value(self, arr: np.ndarray | None, row_idx: int, col_idx: int) -> float | None:
        if arr is None:
            return None
        value = float(arr[row_idx, col_idx])
        if not np.isfinite(value):
            return None
        return value

    def _round_optional(self, value: float | None) -> float | None:
        if value is None:
            return None
        return round(float(value), 6)


def _resolve_data_dir(env_var: str, default_subdir: str) -> Path:
    raw_value = os.getenv(env_var)
    if raw_value:
        return Path(raw_value).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / default_subdir


def _resolve_timestamp(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _grid_id(prefix: str, row_idx: int, col_idx: int) -> str:
    return f"{prefix}_{row_idx}_{col_idx}"


def _cell_geometry_bounds(transform, row_idx: int, col_idx: int) -> tuple[float, float, float, float, float, float]:
    top_left_x, top_left_y = transform * (col_idx, row_idx)
    bottom_right_x, bottom_right_y = transform * (col_idx + 1, row_idx + 1)

    min_lon = min(top_left_x, bottom_right_x)
    max_lon = max(top_left_x, bottom_right_x)
    min_lat = min(top_left_y, bottom_right_y)
    max_lat = max(top_left_y, bottom_right_y)
    centroid_lon = (min_lon + max_lon) / 2
    centroid_lat = (min_lat + max_lat) / 2

    return min_lon, min_lat, max_lon, max_lat, centroid_lon, centroid_lat


def _import_rasterio():
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("rasterio is required. Install with: uv add rasterio") from exc
    return rasterio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract tabular forest features from processed rasters")
    parser.add_argument("--ndvi", help="NDVI raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--ndmi", help="NDMI raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--evi", help="EVI raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--vv", help="VV raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--vh", help="VH raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--vv-vh-ratio", help="VV/VH ratio raster filename in PROCESSED_DATA_DIR")
    parser.add_argument("--ndvi-baseline", help="Baseline NDVI raster filename for NDVI trend")
    parser.add_argument("--output-csv", help="Output features CSV filename")
    parser.add_argument("--write-to-db", choices=["true", "false"], help="Insert extracted rows into PostgreSQL")
    parser.add_argument("--timestamp", help="Capture timestamp (ISO format)")
    parser.add_argument("--source", help="Source name for forest_features rows")
    parser.add_argument("--grid-prefix", help="Prefix for generated grid_id values")
    return parser


def _config_from_args(args: argparse.Namespace) -> FeatureExtractorConfig:
    config = FeatureExtractorConfig()
    if args.ndvi:
        config.ndvi_filename = args.ndvi
    if args.ndmi:
        config.ndmi_filename = args.ndmi
    if args.evi:
        config.evi_filename = args.evi
    if args.vv:
        config.vv_filename = args.vv
    if args.vh:
        config.vh_filename = args.vh
    if args.vv_vh_ratio:
        config.vv_vh_ratio_filename = args.vv_vh_ratio
    if args.ndvi_baseline:
        config.ndvi_baseline_filename = args.ndvi_baseline
    if args.output_csv:
        config.output_csv = args.output_csv
    if args.write_to_db:
        config.write_to_db = args.write_to_db == "true"
    if args.timestamp:
        config.timestamp_utc = _resolve_timestamp(args.timestamp)
    if args.source:
        config.source_name = args.source
    if args.grid_prefix:
        config.grid_prefix = args.grid_prefix
    return config


def main() -> None:
    args = _build_parser().parse_args()
    config = _config_from_args(args)
    extractor = FeatureExtractor(config)
    summary = extractor.run()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
