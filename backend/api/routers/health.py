from fastapi import APIRouter

from api.schemas import HealthScoreResponse, PolygonRequest
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["health"])
service = ForestMetricsService()


@router.post("/health-score", response_model=HealthScoreResponse)
def post_health_score(payload: PolygonRequest) -> HealthScoreResponse:
    return service.get_health_score(payload.polygon)
