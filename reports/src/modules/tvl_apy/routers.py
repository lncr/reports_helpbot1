from fastapi import APIRouter

from src.modules.tvl_apy.dto import TVLAPYReport
from src.modules.tvl_apy.services import get_tvl_apy

router = APIRouter(prefix="/tvl-n-apy", tags=["reports"])


@router.get("/")
async def generate_tvl_and_apy_report() -> TVLAPYReport:
    """TVL&APY report for given wallets and jettons for specified time period"""
    report = await get_tvl_apy()
    return TVLAPYReport.model_validate(report.to_dict(orient="records"))
