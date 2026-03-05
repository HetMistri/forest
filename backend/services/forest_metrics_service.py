from __future__ import annotations

from api.schemas import (
    DemoMetricsResponse,
    ForecastPoint,
    ForestMetricsResponse,
    HealthForecastResponse,
    HealthScoreResponse,
    NDVIMapResponse,
    RiskAlert,
    RiskAlertsResponse,
    RiskZonesResponse,
    SpeciesCompositionResponse,
    SystemStatusResponse,
    TreeDensityResponse,
)


class ForestMetricsService:
    def _area_km2(self, polygon: list[list[float]]) -> float:
        return round(max(len(polygon) - 2, 1) * 0.85, 2)

    def get_forest_metrics(self, polygon: list[list[float]]) -> ForestMetricsResponse:
        area_km2 = self._area_km2(polygon)
        tree_density = 162.0
        tree_count = int(area_km2 * tree_density * 100)
        return ForestMetricsResponse(
            area_km2=area_km2,
            tree_count=tree_count,
            tree_density=tree_density,
            health_score=68.0,
            risk_level="Moderate",
            species_distribution={"teak": 58.0, "bamboo": 27.0, "mixed": 15.0},
        )

    def get_tree_density(self, polygon: list[list[float]]) -> TreeDensityResponse:
        area_km2 = self._area_km2(polygon)
        tree_density = 162.0
        total_trees = int(area_km2 * tree_density * 100)
        return TreeDensityResponse(tree_density=tree_density, total_trees=total_trees)

    def get_health_score(self, _: list[list[float]]) -> HealthScoreResponse:
        return HealthScoreResponse(health_score=68.0, ndvi_avg=0.72, ndmi_avg=0.41)

    def get_risk_alerts(self, _: list[list[float]]) -> RiskAlertsResponse:
        return RiskAlertsResponse(
            risk_level="Moderate",
            alerts=[
                RiskAlert(
                    type="NDVI_DROP",
                    severity="High",
                    location=[20.35, 73.92],
                )
            ],
        )

    def get_species_composition(self, _: list[list[float]]) -> SpeciesCompositionResponse:
        return SpeciesCompositionResponse(teak=58.0, bamboo=27.0, mixed_deciduous=15.0)

    def get_health_forecast(self, _: list[list[float]]) -> HealthForecastResponse:
        return HealthForecastResponse(
            forecast=[
                ForecastPoint(month="2025-01", health_score=66),
                ForecastPoint(month="2025-02", health_score=65),
                ForecastPoint(month="2025-03", health_score=64),
            ]
        )

    def get_ndvi_map(self) -> NDVIMapResponse:
        return NDVIMapResponse(tile_url="/tiles/ndvi/{z}/{x}/{y}.png")

    def get_risk_zones(self) -> RiskZonesResponse:
        return RiskZonesResponse(
            zones=[
                {
                    "risk": "High",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[73.9, 20.2], [73.91, 20.2], [73.91, 20.21], [73.9, 20.2]]],
                    },
                }
            ]
        )

    def get_system_status(self) -> SystemStatusResponse:
        return SystemStatusResponse(
            satellite_data_loaded=True,
            feature_dataset_rows=45231,
            model_status="ready",
        )

    def get_demo_metrics(self) -> DemoMetricsResponse:
        return DemoMetricsResponse(tree_count=84200, health_score=68.0, risk="Moderate")
