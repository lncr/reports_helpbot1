from datetime import UTC

from dateutil.utils import today
from fastapi import APIRouter, Query
from loguru import logger

from src.core.utils import get_start_and_end_dates_for_request
from src.modules.prices.dto import PricesReport
from src.modules.prices.services.coinmarketcap import (
    get_daily_prices_for_symbols_per_month,
    get_mean_price_for_symbols_per_month,
)

router = APIRouter(prefix="/prices", tags=["reports"])


DEFAULT_SYMBOLS = [
    "ETH",
    "TON",
    "USDC",
    "USDT",
    "USDe",
    "sUSDe",
    "stTON",
]


@router.get("/")
async def get_prices_report(
    *,
    month: int = Query(ge=1, le=12),
    year: int | None = None,
    symbols: list[str] = Query(DEFAULT_SYMBOLS),
) -> PricesReport:
    """Prices report for given wallets and jettons for specified time period"""
    now = today(UTC)
    year = year or now.year
    balance_target_date = None
    if year == now.year and month > now.month:
        month = now.month

    logger.debug(f"Generating report for {month=}")

    _, end_date = get_start_and_end_dates_for_request(month, year)
    if month != now.month or year != now.year:
        balance_target_date = end_date

    prices = await get_mean_price_for_symbols_per_month(symbols, balance_target_date)
    daily_prices = await get_daily_prices_for_symbols_per_month(symbols, balance_target_date)

    return PricesReport(prices=prices, daily_prices=daily_prices)
