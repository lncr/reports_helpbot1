from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import PlainTextResponse
from loguru import logger
from pydantic import ValidationError

from src.modules.metrics.dto import TVLMetrics
from src.modules.metrics.services.metrics import generate_tvl_metrics

router = APIRouter(prefix="", tags=["metrics"])


@router.get("/metrics", response_class=PlainTextResponse)
async def get_tvl_metrics() -> Response:
    tvl_daily = await generate_tvl_metrics()
    tvl_metrics_last_row = tvl_daily.iloc[-1].to_dict()

    try:
        TVLMetrics.model_validate(tvl_metrics_last_row)
        tvl_metrics_lst = [f"{key} {item}" for key, item in tvl_metrics_last_row.items()]
        return Response("\n".join(tvl_metrics_lst), media_type="text/plain")
    except ValidationError as e:
        logger.exception(e)
        raise HTTPException(status_code=422, detail=e.errors()) from e
