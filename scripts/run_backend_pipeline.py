from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _ensure_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    backend_path = repo_root / "backend"
    if str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run backend data pipeline: ingestion -> preprocessing -> feature extraction"
    )
    parser.add_argument("--skip-ingestion", action="store_true", help="Skip Earth Engine download stage")
    parser.add_argument("--skip-processing", action="store_true", help="Skip NDVI/NDMI preprocessing stage")
    parser.add_argument("--skip-extraction", action="store_true", help="Skip feature extraction stage")
    parser.add_argument(
        "--write-to-db",
        choices=["true", "false"],
        default=None,
        help="Override FEATURES_WRITE_TO_DB for extraction stage",
    )
    return parser


def main() -> None:
    _ensure_backend_on_path()

    args = _build_parser().parse_args()
    if args.write_to_db is not None:
        os.environ["FEATURES_WRITE_TO_DB"] = args.write_to_db

    summary: dict[str, object] = {}

    if not args.skip_ingestion:
        from ingestion.downloader import Sentinel2Downloader

        downloader = Sentinel2Downloader()
        output_path = downloader.download_composite()
        summary["ingestion"] = {"output": str(output_path)}
    else:
        summary["ingestion"] = {"skipped": True}

    if not args.skip_processing:
        from processing.preprocess import Sentinel2Preprocessor

        processor = Sentinel2Preprocessor()
        summary["processing"] = processor.run()
    else:
        summary["processing"] = {"skipped": True}

    if not args.skip_extraction:
        from features.extractor import FeatureExtractor

        extractor = FeatureExtractor()
        summary["extraction"] = extractor.run()
    else:
        summary["extraction"] = {"skipped": True}

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
