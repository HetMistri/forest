from fastapi import APIRouter

from api.schemas import PolygonRequest, SpeciesCompositionResponse
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["species"])
service = ForestMetricsService()


@router.post("/species-composition", response_model=SpeciesCompositionResponse)
def post_species_composition(payload: PolygonRequest) -> SpeciesCompositionResponse:
    return service.get_species_composition(payload.polygon)
