from fastapi import APIRouter

from api.schemas import PolygonRequest, RiskAlertsResponse, RiskZonesResponse
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["risk"])
service = ForestMetricsService()


@router.post("/risk-alerts", response_model=RiskAlertsResponse)
def post_risk_alerts(payload: PolygonRequest) -> RiskAlertsResponse:
    return service.get_risk_alerts(payload.polygon)


@router.get("/risk-zones", response_model=RiskZonesResponse)
def get_risk_zones() -> RiskZonesResponse:
    return service.get_risk_zones()
