from __future__ import annotations

from typing import List

from pydantic import BaseModel, ConfigDict, Field


class ForestMetricsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    polygon: List[List[float]] = Field(
        ..., description="Polygon coordinates as an array of [lon, lat] pairs"
    )


class ForestMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    area_km2: float
    tree_count: int
    tree_density: float
    health_score: float
    risk_level: str
    species_distribution: dict[str, float]
