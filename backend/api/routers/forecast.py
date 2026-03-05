from fastapi import APIRouter

from api.schemas import HealthForecastResponse, PolygonRequest
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["forecast"])
service = ForestMetricsService()


@router.post("/health-forecast", response_model=HealthForecastResponse)
def post_health_forecast(payload: PolygonRequest) -> HealthForecastResponse:
    return service.get_health_forecast(payload.polygon)
