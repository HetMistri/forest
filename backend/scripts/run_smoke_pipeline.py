from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from sqlalchemy import text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.db import get_engine
from features.extractor import FeatureExtractor, FeatureExtractorConfig
from ingestion.downloader import IngestionConfig, Sentinel2Downloader
from processing.preprocess import PreprocessConfig, Sentinel2Preprocessor


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run smoke pipeline: download -> preprocess -> extract -> DB check")
    parser.add_argument("--start-date", default="2025-12-01")
    parser.add_argument("--end-date", default="2026-01-31")
    parser.add_argument("--bbox", default="73.900,20.200,73.910,20.210")
    parser.add_argument("--scale", type=int, default=30)
    parser.add_argument("--source", default="smoke_pipeline")
    parser.add_argument("--output-prefix", default="smoke_pipeline")
    return parser.parse_args()


def parse_bbox(raw: str) -> tuple[float, float, float, float]:
    parts = [float(v.strip()) for v in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be min_lon,min_lat,max_lon,max_lat")
    return (parts[0], parts[1], parts[2], parts[3])


def main() -> None:
    args = parse_args()

    backend_root = Path(__file__).resolve().parents[1]
    repo_root = backend_root.parent
    load_dotenv(backend_root / ".env")

    os.environ.setdefault("RAW_DATA_DIR", str(repo_root / "data" / "raw"))
    os.environ.setdefault("PROCESSED_DATA_DIR", str(repo_root / "data" / "processed"))

    download_name = f"{args.output_prefix}_s2.tif"
    ndvi_name = f"{args.output_prefix}_ndvi.tif"
    ndmi_name = f"{args.output_prefix}_ndmi.tif"
    evi_name = f"{args.output_prefix}_evi.tif"
    features_name = f"{args.output_prefix}_features.csv"

    download_path = Sentinel2Downloader(
        IngestionConfig(
            start_date=args.start_date,
            end_date=args.end_date,
            region_bbox=parse_bbox(args.bbox),
            scale_meters=args.scale,
            output_name=download_name,
        )
    ).download_composite()

    processing = Sentinel2Preprocessor(
        PreprocessConfig(
            input_filename=download_name,
            ndvi_filename=ndvi_name,
            ndmi_filename=ndmi_name,
            evi_filename=evi_name,
        )
    ).run()

    extraction = FeatureExtractor(
        FeatureExtractorConfig(
            ndvi_filename=ndvi_name,
            ndmi_filename=ndmi_name,
            evi_filename=evi_name,
            output_csv=features_name,
            source_name=args.source,
            write_to_db=True,
            grid_prefix=args.output_prefix,
        )
    ).run()

    engine = get_engine()
    if engine is None:
        raise RuntimeError("DATABASE_URL is required to verify DB inserts")

    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT COUNT(*) FROM forest_features WHERE source = :source"),
            {"source": args.source},
        ).scalar_one()

    summary = {
        "download": str(download_path),
        "processing": processing,
        "extraction": extraction,
        "db_rows_for_source": int(rows),
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
