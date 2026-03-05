from fastapi import APIRouter

from api.schemas import ForestMetricsRequest, ForestMetricsResponse
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["forest-metrics"])
service = ForestMetricsService()


@router.post("/forest-metrics", response_model=ForestMetricsResponse)
def post_forest_metrics(payload: ForestMetricsRequest) -> ForestMetricsResponse:
    return service.get_forest_metrics(payload.polygon)
