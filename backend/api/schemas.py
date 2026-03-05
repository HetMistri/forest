from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolygonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    polygon: list[list[float]] = Field(
        ...,
        min_length=4,
        description="Polygon coordinates as an array of [lon, lat] pairs",
    )

    @field_validator("polygon")
    @classmethod
    def validate_polygon(cls, value: list[list[float]]) -> list[list[float]]:
        for point in value:
            if len(point) != 2:
                raise ValueError("Each polygon point must contain exactly [lon, lat]")
        return value


class ForestMetricsRequest(PolygonRequest):
    pass


class ForestMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area_km2: float
    tree_count: int
    tree_density: float
    health_score: float
    risk_level: str
    species_distribution: dict[str, float]


class TreeDensityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_density: float
    total_trees: int


class HealthScoreResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    health_score: float
    ndvi_avg: float
    ndmi_avg: float


class RiskAlert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    severity: Literal["Low", "Moderate", "High"]
    location: list[float]


class RiskAlertsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: Literal["Low", "Moderate", "High"]
    alerts: list[RiskAlert]


class SpeciesCompositionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    teak: float
    bamboo: float
    mixed_deciduous: float


class ForecastPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    health_score: float


class HealthForecastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    forecast: list[ForecastPoint]


class NDVIMapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tile_url: str


class RiskZone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk: Literal["Low", "Moderate", "High"]
    geometry: dict[str, Any]


class RiskZonesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zones: list[RiskZone]


class SystemStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    satellite_data_loaded: bool
    feature_dataset_rows: int
    model_status: str


class DemoMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tree_count: int
    health_score: float
    risk: str
