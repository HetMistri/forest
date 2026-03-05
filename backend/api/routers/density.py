from fastapi import APIRouter

from api.schemas import PolygonRequest, TreeDensityResponse
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["density"])
service = ForestMetricsService()


@router.post("/tree-density", response_model=TreeDensityResponse)
def post_tree_density(payload: PolygonRequest) -> TreeDensityResponse:
    return service.get_tree_density(payload.polygon)
