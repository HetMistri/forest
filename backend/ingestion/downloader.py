from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.request import urlopen


@dataclass(slots=True)
class IngestionConfig:
    start_date: str = field(default_factory=lambda: os.getenv("INGESTION_START_DATE", "2024-01-01"))
    end_date: str = field(default_factory=lambda: os.getenv("INGESTION_END_DATE", date.today().isoformat()))
    max_cloud_pct: float = field(default_factory=lambda: float(os.getenv("INGESTION_MAX_CLOUD_PCT", "20")))
    scale_meters: int = field(default_factory=lambda: int(os.getenv("INGESTION_SCALE_METERS", "10")))
    region_bbox: tuple[float, float, float, float] = field(
        default_factory=lambda: _parse_bbox(os.getenv("INGESTION_REGION_BBOX", "73.55,20.05,74.25,21.10"))
    )
    region_geojson_path: str | None = field(default_factory=lambda: os.getenv("INGESTION_REGION_GEOJSON"))
    region_polygon: list[list[float]] | None = None
    gee_project: str | None = field(default_factory=lambda: os.getenv("GEE_PROJECT"))
    gee_service_account: str | None = field(default_factory=lambda: os.getenv("GEE_SERVICE_ACCOUNT"))
    gee_private_key_file: str | None = field(default_factory=lambda: os.getenv("GEE_PRIVATE_KEY_FILE"))
    interactive_auth: bool = field(
        default_factory=lambda: os.getenv("INGESTION_INTERACTIVE_AUTH", "false").lower() == "true"
    )
    bands: tuple[str, ...] = field(default_factory=lambda: _parse_bands(os.getenv("INGESTION_BANDS", "B4,B8,B11")))
    output_name: str = field(default_factory=lambda: os.getenv("INGESTION_OUTPUT_NAME", "sentinel2_composite.tif"))
    output_dir: Path = field(default_factory=lambda: _default_output_dir())

    def validate(self) -> None:
        try:
            date.fromisoformat(self.start_date)
            date.fromisoformat(self.end_date)
        except ValueError as exc:
            raise ValueError("start_date and end_date must be ISO format: YYYY-MM-DD") from exc

        if self.start_date > self.end_date:
            raise ValueError("start_date cannot be later than end_date")

        if not (0 <= self.max_cloud_pct <= 100):
            raise ValueError("max_cloud_pct must be within 0..100")

        if self.scale_meters <= 0:
            raise ValueError("scale_meters must be > 0")

        if len(self.bands) == 0:
            raise ValueError("bands cannot be empty")

        if self.region_polygon is not None:
            if len(self.region_polygon) < 3:
                raise ValueError("region_polygon must contain at least 3 points")
            for point in self.region_polygon:
                if len(point) != 2:
                    raise ValueError("Each region polygon point must contain [lon, lat]")


class Sentinel2Downloader:
    """Downloads Sentinel-2 composite imagery from Google Earth Engine."""

    def __init__(self, config: IngestionConfig | None = None) -> None:
        self.config = config or IngestionConfig()
        self.config.validate()

    def initialize_earth_engine(self) -> None:
        ee = _import_ee()

        if self.config.gee_service_account and self.config.gee_private_key_file:
            credentials = ee.ServiceAccountCredentials(
                self.config.gee_service_account,
                self.config.gee_private_key_file,
            )
            ee.Initialize(credentials=credentials, project=self.config.gee_project)
            return

        try:
            ee.Initialize(project=self.config.gee_project)
        except Exception as exc:
            if not self.config.interactive_auth:
                raise RuntimeError(
                    "Earth Engine initialization failed. Configure service-account credentials "
                    "or set INGESTION_INTERACTIVE_AUTH=true for local interactive login."
                ) from exc

            ee.Authenticate()
            ee.Initialize(project=self.config.gee_project)

    def build_region(self) -> Any:
        ee = _import_ee()

        if self.config.region_polygon:
            polygon = _ensure_closed_ring(self.config.region_polygon)
            return ee.Geometry.Polygon([polygon])

        if self.config.region_geojson_path:
            geojson_path = Path(self.config.region_geojson_path)
            if not geojson_path.exists():
                raise FileNotFoundError(f"Region GeoJSON file not found: {geojson_path}")

            payload = json.loads(geojson_path.read_text(encoding="utf-8"))
            geometry = _extract_geojson_geometry(payload)
            return ee.Geometry(geometry)

        min_lon, min_lat, max_lon, max_lat = self.config.region_bbox
        return ee.Geometry.BBox(min_lon, min_lat, max_lon, max_lat)

    def build_collection(self, region: Any) -> Any:
        ee = _import_ee()
        collection = (
            ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
            .filterDate(self.config.start_date, self.config.end_date)
            .filterBounds(region)
            .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", self.config.max_cloud_pct))
        )
        return collection

    def build_composite(self, region: Any) -> Any:
        collection = self.build_collection(region)
        selected = collection.select(list(self.config.bands))
        return selected.median().clip(region)

    def download_composite(self) -> Path:
        self.initialize_earth_engine()
        region = self.build_region()
        composite = self.build_composite(region)

        output_dir = self.config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / self.config.output_name

        download_url = composite.getDownloadURL(
            {
                "name": output_path.stem,
                "format": "GEO_TIFF",
                "region": region.getInfo()["coordinates"],
                "crs": "EPSG:4326",
                "scale": self.config.scale_meters,
            }
        )

        _download_file(download_url, output_path)
        self._write_metadata(output_path)
        return output_path

    def _write_metadata(self, output_path: Path) -> None:
        metadata = {
            "dataset": "COPERNICUS/S2_SR_HARMONIZED",
            "start_date": self.config.start_date,
            "end_date": self.config.end_date,
            "max_cloud_pct": self.config.max_cloud_pct,
            "scale_meters": self.config.scale_meters,
            "bands": list(self.config.bands),
            "region_bbox": list(self.config.region_bbox),
            "region_polygon": self.config.region_polygon,
            "output_file": str(output_path),
        }
        output_path.with_suffix(".metadata.json").write_text(
            json.dumps(metadata, indent=2),
            encoding="utf-8",
        )


def _default_output_dir() -> Path:
    env_path = os.getenv("RAW_DATA_DIR")
    if env_path:
        return Path(env_path).expanduser().resolve()

    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "data" / "raw"


def _parse_bbox(raw: str) -> tuple[float, float, float, float]:
    values = [part.strip() for part in raw.split(",")]
    if len(values) != 4:
        raise ValueError("INGESTION_REGION_BBOX must be min_lon,min_lat,max_lon,max_lat")
    min_lon, min_lat, max_lon, max_lat = [float(value) for value in values]
    return (min_lon, min_lat, max_lon, max_lat)


def _parse_bands(raw: str) -> tuple[str, ...]:
    parsed = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not parsed:
        raise ValueError("INGESTION_BANDS cannot be empty")
    return parsed


def _extract_geojson_geometry(payload: dict[str, Any]) -> dict[str, Any]:
    payload_type = payload.get("type")

    if payload_type == "FeatureCollection":
        features = payload.get("features") or []
        if not features:
            raise ValueError("GeoJSON FeatureCollection has no features")
        geometry = features[0].get("geometry")
        if not geometry:
            raise ValueError("First feature has no geometry")
        return geometry

    if payload_type == "Feature":
        geometry = payload.get("geometry")
        if not geometry:
            raise ValueError("GeoJSON Feature has no geometry")
        return geometry

    if payload_type in {"Polygon", "MultiPolygon"}:
        return payload

    raise ValueError("Unsupported GeoJSON payload for region geometry")


def _ensure_closed_ring(polygon: list[list[float]]) -> list[list[float]]:
    closed = [point[:] for point in polygon]
    if closed[0] != closed[-1]:
        closed.append(closed[0][:])
    return closed


def _import_ee() -> Any:
    try:
        import ee  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "earthengine-api is not installed. Install it with: uv add earthengine-api"
        ) from exc
    return ee


def _download_file(url: str, output_path: Path) -> None:
    with urlopen(url) as response:  # noqa: S310
        output_path.write_bytes(response.read())


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download Sentinel-2 composite from Google Earth Engine")
    parser.add_argument("--start-date", help="ISO start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="ISO end date (YYYY-MM-DD)")
    parser.add_argument("--region-geojson", help="Path to GeoJSON file for region boundary")
    parser.add_argument("--region-bbox", help="min_lon,min_lat,max_lon,max_lat")
    parser.add_argument("--max-cloud-pct", type=float, help="Maximum cloud coverage percentage")
    parser.add_argument("--scale", type=int, help="Output resolution in meters")
    parser.add_argument("--bands", help="Comma-separated Sentinel-2 band names (e.g. B4,B8,B11)")
    parser.add_argument("--output", help="Output raster filename")
    parser.add_argument("--interactive-auth", choices=["true", "false"], help="Enable interactive ee.Authenticate")
    return parser


def _config_from_args(args: argparse.Namespace) -> IngestionConfig:
    config = IngestionConfig()

    if args.start_date:
        config.start_date = args.start_date
    if args.end_date:
        config.end_date = args.end_date
    if args.region_geojson:
        config.region_geojson_path = args.region_geojson
    if args.region_bbox:
        config.region_bbox = _parse_bbox(args.region_bbox)
    if args.max_cloud_pct is not None:
        config.max_cloud_pct = args.max_cloud_pct
    if args.scale is not None:
        config.scale_meters = args.scale
    if args.bands:
        config.bands = _parse_bands(args.bands)
    if args.output:
        config.output_name = args.output
    if args.interactive_auth:
        config.interactive_auth = args.interactive_auth == "true"

    config.validate()
    return config


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()
    config = _config_from_args(args)
    downloader = Sentinel2Downloader(config)
    output_file = downloader.download_composite()
    print(f"Downloaded Sentinel-2 composite to: {output_file}")


if __name__ == "__main__":
    main()
