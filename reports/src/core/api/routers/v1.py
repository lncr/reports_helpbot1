from fastapi import APIRouter

from src.modules.balances.routers import router as balances_router
from src.modules.prices.routers import router as prices_router
from src.modules.reports.routers import router as report_all_router
from src.modules.transfers.routers import router as transfers_router
from src.modules.tvl_apy.routers import router as tvl_apy_router
from src.modules.helpbot import router as helpbot_router

__all__ = ("router",)

router = APIRouter(prefix="/v1")
router.include_router(balances_router)
router.include_router(prices_router)
router.include_router(transfers_router)
router.include_router(tvl_apy_router)
router.include_router(report_all_router)
router.include_router(helpbot_router)
