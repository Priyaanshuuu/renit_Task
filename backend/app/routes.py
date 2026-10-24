from fastapi import APIRouter

from .schemas import HealthResponse

router = APIRouter(prefix="/api")


@router.get(
    "/health",
    tags=["Health"],
    summary="Check API process health",
    description="Confirms the API responds. Does not check source data or snapshot readiness.",
)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")
