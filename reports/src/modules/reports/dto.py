from src.core.dto import BaseDTO
from src.modules.balances.dto import BalancesReport
from src.modules.prices.dto import DailyPrices, Prices
from src.modules.transfers.dto import TransfersReport
from src.modules.tvl_apy.dto import TVLAPYReport


class ReportResponse(BaseDTO):
    transfers: TransfersReport
    balances: BalancesReport
    tvl_apy: TVLAPYReport
    prices: Prices
    daily_prices: DailyPrices
