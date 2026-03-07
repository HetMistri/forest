from fastapi import APIRouter

from api.schemas import (
    DemoMetricsResponse,
    PipelineStatusRequest,
    PipelineStatusResponse,
    SystemStatusResponse,
)
from services.forest_metrics_service import ForestMetricsService

router = APIRouter(tags=["system"])
service = ForestMetricsService()


@router.get("/system-status", response_model=SystemStatusResponse)
def get_system_status() -> SystemStatusResponse:
    return service.get_system_status()


@router.get("/demo-metrics", response_model=DemoMetricsResponse)
def get_demo_metrics() -> DemoMetricsResponse:
    return service.get_demo_metrics()


@router.post("/pipeline-status", response_model=PipelineStatusResponse)
def post_pipeline_status(payload: PipelineStatusRequest) -> PipelineStatusResponse:
    return service.get_pipeline_status(payload.polygon)
