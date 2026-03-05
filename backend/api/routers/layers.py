from fastapi import APIRouter

from api.schemas import NDVIMapResponse
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["layers"])
service = ForestMetricsService()


@router.get("/ndvi-map", response_model=NDVIMapResponse)
def get_ndvi_map() -> NDVIMapResponse:
    return service.get_ndvi_map()
