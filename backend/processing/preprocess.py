from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


@dataclass(slots=True)
class PreprocessConfig:
    raw_data_dir: Path = field(default_factory=lambda: _resolve_data_dir("RAW_DATA_DIR", "raw"))
    processed_data_dir: Path = field(default_factory=lambda: _resolve_data_dir("PROCESSED_DATA_DIR", "processed"))
    input_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_INPUT_NAME", "sentinel2_composite.tif"))
    ndvi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDVI_NAME", "ndvi.tif"))
    ndmi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_NDMI_NAME", "ndmi.tif"))
    evi_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_EVI_NAME", "evi.tif"))
    sentinel1_input_filename: str = field(
        default_factory=lambda: os.getenv("PROCESSING_S1_INPUT_NAME", "sentinel1_composite.tif")
    )
    vv_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_VV_NAME", "vv.tif"))
    vh_filename: str = field(default_factory=lambda: os.getenv("PROCESSING_VH_NAME", "vh.tif"))
    vv_vh_ratio_filename: str = field(
        default_factory=lambda: os.getenv("PROCESSING_VV_VH_RATIO_NAME", "vv_vh_ratio.tif")
    )
    blue_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_BLUE_BAND_INDEX", "1")))
    red_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_RED_BAND_INDEX", "2")))
    nir_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_NIR_BAND_INDEX", "3")))
    swir_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_SWIR_BAND_INDEX", "4")))
    vv_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_VV_BAND_INDEX", "1")))
    vh_band_index: int = field(default_factory=lambda: int(os.getenv("PROCESSING_VH_BAND_INDEX", "2")))
    clip_min: float = field(default_factory=lambda: float(os.getenv("PROCESSING_CLIP_MIN", "-1.0")))
    clip_max: float = field(default_factory=lambda: float(os.getenv("PROCESSING_CLIP_MAX", "1.0")))

    def validate(self) -> None:
        if (
            self.blue_band_index <= 0
            or self.red_band_index <= 0
            or self.nir_band_index <= 0
            or self.swir_band_index <= 0
            or self.vv_band_index <= 0
            or self.vh_band_index <= 0
        ):
            raise ValueError("Band indices must be positive and 1-based")
        if self.clip_min >= self.clip_max:
            raise ValueError("clip_min must be smaller than clip_max")


class Sentinel2Preprocessor:
    """Preprocesses Sentinel-2 composite raster into NDVI, NDMI, and EVI outputs."""

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
        evi_path = self.config.processed_data_dir / self.config.evi_filename

        with rasterio.open(source_path) as src:
            blue = src.read(self.config.blue_band_index).astype(np.float32)
            red = src.read(self.config.red_band_index).astype(np.float32)
            nir = src.read(self.config.nir_band_index).astype(np.float32)
            swir = src.read(self.config.swir_band_index).astype(np.float32)
            profile = src.profile

        ndvi = self._safe_index(numerator=nir - red, denominator=nir + red)
        ndmi = self._safe_index(numerator=nir - swir, denominator=nir + swir)
        evi = self._safe_evi(nir=nir, red=red, blue=blue)

        out_profile = profile.copy()
        out_profile.update(dtype=rasterio.float32, count=1, compress="lzw")

        with rasterio.open(ndvi_path, "w", **out_profile) as dst:
            dst.write(ndvi, 1)

        with rasterio.open(ndmi_path, "w", **out_profile) as dst:
            dst.write(ndmi, 1)

        with rasterio.open(evi_path, "w", **out_profile) as dst:
            dst.write(evi, 1)

        metadata_path = self.config.processed_data_dir / "preprocess.metadata.json"
        metadata = {
            "source_raster": str(source_path),
            "ndvi_raster": str(ndvi_path),
            "ndmi_raster": str(ndmi_path),
            "evi_raster": str(evi_path),
            "blue_band_index": self.config.blue_band_index,
            "red_band_index": self.config.red_band_index,
            "nir_band_index": self.config.nir_band_index,
            "swir_band_index": self.config.swir_band_index,
            "clip_min": self.config.clip_min,
            "clip_max": self.config.clip_max,
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "ndvi": str(ndvi_path),
            "ndmi": str(ndmi_path),
            "evi": str(evi_path),
            "metadata": str(metadata_path),
        }

    def _safe_index(self, numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
        eps = 1e-8
        ratio = numerator / (denominator + eps)
        ratio = np.where(np.isfinite(ratio), ratio, np.nan)
        ratio = np.clip(ratio, self.config.clip_min, self.config.clip_max)
        return ratio.astype(np.float32)

    def _safe_evi(self, nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
        eps = 1e-8
        ratio = 2.5 * ((nir - red) / (nir + (6.0 * red) - (7.5 * blue) + 1.0 + eps))
        ratio = np.where(np.isfinite(ratio), ratio, np.nan)
        ratio = np.clip(ratio, self.config.clip_min, self.config.clip_max)
        return ratio.astype(np.float32)


class Sentinel1Preprocessor:
    """Preprocesses Sentinel-1 composite raster into VV, VH, and VV/VH ratio outputs."""

    def __init__(self, config: PreprocessConfig | None = None) -> None:
        self.config = config or PreprocessConfig()
        self.config.validate()

    def run(self) -> dict[str, str]:
        rasterio = _import_rasterio()

        source_path = self.config.raw_data_dir / self.config.sentinel1_input_filename
        if not source_path.exists():
            raise FileNotFoundError(f"Input raster not found: {source_path}")

        self.config.processed_data_dir.mkdir(parents=True, exist_ok=True)
        vv_path = self.config.processed_data_dir / self.config.vv_filename
        vh_path = self.config.processed_data_dir / self.config.vh_filename
        ratio_path = self.config.processed_data_dir / self.config.vv_vh_ratio_filename

        with rasterio.open(source_path) as src:
            vv = src.read(self.config.vv_band_index).astype(np.float32)
            vh = src.read(self.config.vh_band_index).astype(np.float32)
            profile = src.profile

        vv_vh_ratio = self._safe_ratio(vv=vv, vh=vh)

        out_profile = profile.copy()
        out_profile.update(dtype=rasterio.float32, count=1, compress="lzw")

        with rasterio.open(vv_path, "w", **out_profile) as dst:
            dst.write(vv, 1)

        with rasterio.open(vh_path, "w", **out_profile) as dst:
            dst.write(vh, 1)

        with rasterio.open(ratio_path, "w", **out_profile) as dst:
            dst.write(vv_vh_ratio, 1)

        metadata_path = self.config.processed_data_dir / "preprocess_sentinel1.metadata.json"
        metadata = {
            "source_raster": str(source_path),
            "vv_raster": str(vv_path),
            "vh_raster": str(vh_path),
            "vv_vh_ratio_raster": str(ratio_path),
            "vv_band_index": self.config.vv_band_index,
            "vh_band_index": self.config.vh_band_index,
            "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return {
            "vv": str(vv_path),
            "vh": str(vh_path),
            "vv_vh_ratio": str(ratio_path),
            "metadata": str(metadata_path),
        }

    def _safe_ratio(self, vv: np.ndarray, vh: np.ndarray) -> np.ndarray:
        eps = 1e-8
        ratio = vv / (vh + eps)
        ratio = np.where(np.isfinite(ratio), ratio, np.nan)
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
    parser = argparse.ArgumentParser(description="Compute Sentinel-2 indices and Sentinel-1 SAR features")
    parser.add_argument("--input", help="Input filename in RAW_DATA_DIR")
    parser.add_argument("--s1-input", help="Sentinel-1 input filename in RAW_DATA_DIR")
    parser.add_argument("--ndvi-output", help="Output NDVI filename in PROCESSED_DATA_DIR")
    parser.add_argument("--ndmi-output", help="Output NDMI filename in PROCESSED_DATA_DIR")
    parser.add_argument("--evi-output", help="Output EVI filename in PROCESSED_DATA_DIR")
    parser.add_argument("--vv-output", help="Output VV filename in PROCESSED_DATA_DIR")
    parser.add_argument("--vh-output", help="Output VH filename in PROCESSED_DATA_DIR")
    parser.add_argument("--ratio-output", help="Output VV/VH ratio filename in PROCESSED_DATA_DIR")
    parser.add_argument("--blue-band", type=int, help="1-based index of blue band")
    parser.add_argument("--red-band", type=int, help="1-based index of red band")
    parser.add_argument("--nir-band", type=int, help="1-based index of NIR band")
    parser.add_argument("--swir-band", type=int, help="1-based index of SWIR band")
    parser.add_argument("--vv-band", type=int, help="1-based index of VV band in Sentinel-1 raster")
    parser.add_argument("--vh-band", type=int, help="1-based index of VH band in Sentinel-1 raster")
    parser.add_argument("--with-s1", choices=["true", "false"], default="true")
    return parser


def _config_from_args(args: argparse.Namespace) -> PreprocessConfig:
    config = PreprocessConfig()

    if args.input:
        config.input_filename = args.input
    if args.s1_input:
        config.sentinel1_input_filename = args.s1_input
    if args.ndvi_output:
        config.ndvi_filename = args.ndvi_output
    if args.ndmi_output:
        config.ndmi_filename = args.ndmi_output
    if args.evi_output:
        config.evi_filename = args.evi_output
    if args.vv_output:
        config.vv_filename = args.vv_output
    if args.vh_output:
        config.vh_filename = args.vh_output
    if args.ratio_output:
        config.vv_vh_ratio_filename = args.ratio_output
    if args.blue_band is not None:
        config.blue_band_index = args.blue_band
    if args.red_band is not None:
        config.red_band_index = args.red_band
    if args.nir_band is not None:
        config.nir_band_index = args.nir_band
    if args.swir_band is not None:
        config.swir_band_index = args.swir_band
    if args.vv_band is not None:
        config.vv_band_index = args.vv_band
    if args.vh_band is not None:
        config.vh_band_index = args.vh_band

    config.validate()
    return config


def main() -> None:
    args = _build_parser().parse_args()
    config = _config_from_args(args)
    outputs = {"sentinel2": Sentinel2Preprocessor(config).run()}
    if args.with_s1 == "true":
        outputs["sentinel1"] = Sentinel1Preprocessor(config).run()
    print(json.dumps(outputs, indent=2))


if __name__ == "__main__":
    main()
