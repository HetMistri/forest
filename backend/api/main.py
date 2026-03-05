from fastapi import FastAPI

from .schemas import ForestMetricsRequest, ForestMetricsResponse

app = FastAPI(title="Forest Analytics API")


@app.post("/forest-metrics", response_model=ForestMetricsResponse)
def post_forest_metrics(payload: ForestMetricsRequest) -> ForestMetricsResponse:
    polygon_size = len(payload.polygon)
    area_km2 = round(max(polygon_size - 2, 1) * 0.85, 2)
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
