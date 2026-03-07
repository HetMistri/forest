from fastapi import APIRouter

from .density import router as density_router
from .forecast import router as forecast_router
from .forest_metrics import router as forest_metrics_router
from .health import router as health_router
from .layers import router as layers_router
from .risk import router as risk_router
from .species import router as species_router
from .system import router as system_router
from .action_plan import router as action_plan_router

api_router = APIRouter()
api_router.include_router(forest_metrics_router)
api_router.include_router(density_router)
api_router.include_router(health_router)
api_router.include_router(risk_router)
api_router.include_router(species_router)
api_router.include_router(forecast_router)
api_router.include_router(layers_router)
api_router.include_router(system_router)
api_router.include_router(action_plan_router)
