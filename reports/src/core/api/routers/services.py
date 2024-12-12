from fastapi import APIRouter, status

router = APIRouter(prefix="", tags=["services"])


@router.get("/trigger-error/", include_in_schema=False)
async def trigger_error() -> float:
    return 1 / 0


@router.get(
    "/health/",
    summary="Perform a Health Check",
    response_description="Return HTTP Status Code 200 (OK)",
    status_code=status.HTTP_200_OK,
)
async def health_check() -> None: ...
