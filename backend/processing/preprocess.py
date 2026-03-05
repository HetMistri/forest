from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class PreprocessConfig:
    raw_data_dir: Path = field(default_factory=lambda: _resolve_data_dir("RAW_DATA_DIR", "raw"))
    processed_data_dir: Path = field(default_factory=lambda: _resolve_data_dir("PROCESSED_DATA_DIR", "processed"))
    input_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_INPUT_NAME", "sentinel2_composite.tif"))
    ndvi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDVI_NAME", "ndvi.tif"))
    ndmi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDMI_NAME", "ndmi.tif"))
    red_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_RED_BAND_INDEX", "1")))
    nir_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_NIR_BAND_INDEX", "2")))
    swir_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_SWIR_BAND_INDEX", "3")))
    clip_min: float = field(default_factory=lambda: float(os.getenv("PROCESSING_CLIP_MIN", "-1.0")))
    clip_max: float = field(default_factory=lambda: float(os.getenv("PROCESSING_CLIP_MAX", "1.0")))

    def validate(self) -> None:
        if self.red_band_index <= 0 or self.nir_band_index <= 0 or self.swir_band_index <= 0:
            raise ValueError("Band indices must be positive and 1-based")
        if self.clip_min >= self.clip_max:
            raise ValueError("clip_min must be smaller than clip_max")


class Sentinel2Preprocessor:
    """Preprocesses Sentinel-2 composite raster into NDVI and NDMI outputs."""

    def __init__(self, config: PreprocessConfig | None = None) -> None:
        self.config = config or PreprocessConfig()
        self.config.validate()

    def run(self) -> dict[str, str]:
        rasterio = _import_rasterio()

        source_path = self.config.raw_data_dir / self.config.input_filename
        if not source_path.exists():
            raise FileNotFoundError(f"Input raster not found: {source_path}")

        self.config.processed_data_dir.mkdir(parents=True, exist_ok=True)
        ndvi_path = self.config.processed_data_dir / self.config.ndvi_filename
        ndmi_path = self.config.processed_data_dir / self.config.ndmi_filename

        with rasterio.open(source_path) as src:
            red = src.read(self.config.red_band_index).astype(np.float32)
            nir = src.read(self.config.nir_band_index).astype(np.float32)
            swir = src.read(self.config.swir_band_index).astype(np.float32)
            profile = src.profile

        ndvi = self._safe_index(numerator=nir - red, denominator=nir + red)
        ndmi = self._safe_index(numerator=nir - swir, denominator=nir + swir)

        out_profile = profile.copy()
        out_profile.update(dtype=rasterio.float32, count=1, compress="lzw")

        with rasterio.open(ndvi_path, "w", **out_profile) as dst:
            dst.write(ndvi, 1)

        with rasterio.open(ndmi_path, "w", **out_profile) as dst:
            dst.write(ndmi, 1)

        metadata_path = self.config.processed_data_dir / "preprocess.metadata.json"
        metadata = {
            "source_raster": str(source_path),
            "ndvi_raster": str(ndvi_path),
            "ndmi_raster": str(ndmi_path),
            "red_band_index": self.config.red_band_index,
            "nir_band_index": self.config.nir_band_index,
            "swir_band_index": self.config.swir_band_index,
            "clip_min": self.config.clip_min,
            "clip_max": self.config.clip_max,
            "generated_at_utc": datetime.utcnow().isoformat() + "Z",
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "ndvi": str(ndvi_path),
            "ndmi": str(ndmi_path),
            "metadata": str(metadata_path),
        }

    def _safe_index(self, numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
        eps = 1e-8
        ratio = numerator / (denominator + eps)
        ratio = np.where(np.isfinite(ratio), ratio, np.nan)
        ratio = np.clip(ratio, self.config.clip_min, self.config.clip_max)
        return ratio.astype(np.float32)


def _resolve_data_dir(env_var: str, default_subdir: str) -> Path:
    raw_value = os.getenv(env_var)
    if raw_value:
        return Path(raw_value).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / default_subdir


def _import_rasterio():
    try:
        import rasterio
    except ImportError as exc:
        raise RuntimeError("rasterio is required. Install with: uv add rasterio") from exc
    return rasterio


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compute NDVI and NDMI rasters from Sentinel-2 composite")
    parser.add_argument("--input", help="Input filename in RAW_DATA_DIR")
    parser.add_argument("--ndvi-output", help="Output NDVI filename in PROCESSED_DATA_DIR")
    parser.add_argument("--ndmi-output", help="Output NDMI filename in PROCESSED_DATA_DIR")
    parser.add_argument("--red-band", type=int, help="1-based index of red band")
    parser.add_argument("--nir-band", type=int, help="1-based index of NIR band")
    parser.add_argument("--swir-band", type=int, help="1-based index of SWIR band")
    return parser


def _config_from_args(args: argparse.Namespace) -> PreprocessConfig:
    config = PreprocessConfig()

    if args.input:
        config.input_filename = args.input
    if args.ndvi_output:
        config.ndvi_filename = args.ndvi_output
    if args.ndmi_output:
        config.ndmi_filename = args.ndmi_output
    if args.red_band is not None:
        config.red_band_index = args.red_band
    if args.nir_band is not None:
        config.nir_band_index = args.nir_band
    if args.swir_band is not None:
        config.swir_band_index = args.swir_band

    config.validate()
    return config


def main() -> None:
    args = _build_parser().parse_args()
    config = _config_from_args(args)
    processor = Sentinel2Preprocessor(config)
    outputs = processor.run()
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
