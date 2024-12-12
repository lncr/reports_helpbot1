import contextlib
from datetime import UTC

import pandas as pd
from dateutil.utils import today
from fastapi import APIRouter, Query
from loguru import logger

from src.core.const import Network
from src.core.dto import JettonAddressBook, Wallets
from src.core.utils import get_start_and_end_dates_for_request, get_wallet_network
from src.modules.balances.dto import BalancesReport
from src.modules.balances.services.eth import get_eth_wallet_balance
from src.modules.balances.services.jettons import get_jetton_balance
from src.modules.balances.services.ton import get_ton_balance
from src.modules.prices.services.coinmarketcap import (
    get_daily_prices_for_symbols_per_month,
    get_mean_price_for_symbols_per_month,
)
from src.modules.reports.dto import ReportResponse
from src.modules.transfers.dto import TransfersReport
from src.modules.transfers.services.eth import get_eth_wallet_token_transfers
from src.modules.transfers.services.ton import get_ton_transfers
from src.modules.tvl_apy.dto import TVLAPYReport
from src.modules.tvl_apy.services import get_tvl_apy

router = APIRouter(prefix="/all", tags=["reports"], deprecated=True)


DEFAULT_SYMBOLS = [
    "ETH",
    "TON",
    "USDC",
    "USDT",
    "USDe",
    "sUSDe",
    "stTON",
]


@router.post("/")
async def generate_whole_report(
    *,
    wallets: Wallets,
    jettons: JettonAddressBook,
    month: int = Query(ge=1, le=12),
    year: int | None = None,
    symbols: list[str] = Query(DEFAULT_SYMBOLS),
) -> ReportResponse:
    """
    Generate report for all given wallets for specified time period:
     1. balances
     2. transfers
     3. prices
     4. TVL & APY
    """
    now = today(UTC)
    year = year or now.year
    balance_target_date = None
    if year == now.year and month > now.month:
        month = now.month

    logger.debug(f"Generating report for {month=}")

    start_date, end_date = get_start_and_end_dates_for_request(month, year)
    if month != now.month or year != now.year:
        balance_target_date = end_date

    transfers_dfs: list[pd.DataFrame] = []
    balances_dfs: list[pd.DataFrame] = []

    for wallet in wallets.root:
        if get_wallet_network(wallet) is Network.ETH:
            transfers_report = await get_eth_wallet_token_transfers(wallet, start_date, end_date)
            balances_report = await get_eth_wallet_balance(wallet, balance_target_date)
            if not balances_report.empty:
                balances_report["date"] = pd.to_datetime(balances_report["date"], errors="coerce").dt.tz_localize(None)
                balances_report["date"] = balances_report["date"].dt.tz_localize("UTC").dt.normalize()
        else:
            transfers_report = await get_ton_transfers(wallet, jettons, start_date, end_date)
            balances_ton_report = await get_ton_balance(wallet, balance_target_date)
            balances_jetton_report = await get_jetton_balance(wallet, jettons, balance_target_date)
            if not balances_ton_report.empty:
                balances_ton_report["date"] = pd.to_datetime(
                    balances_ton_report["date"], errors="coerce"
                ).dt.tz_localize(None)
                balances_ton_report["date"] = balances_ton_report["date"].dt.tz_localize("UTC").dt.normalize()
            if not balances_jetton_report.empty:
                balances_jetton_report["date"] = pd.to_datetime(
                    balances_jetton_report["date"], errors="coerce"
                ).dt.tz_localize(None)
                balances_jetton_report["date"] = balances_jetton_report["date"].dt.tz_localize("UTC").dt.normalize()
            balances_report = pd.concat([balances_ton_report, balances_jetton_report])

        if not transfers_report.empty:
            with contextlib.suppress(KeyError):
                transfers_report["date"] = pd.to_datetime(transfers_report["date"]).dt.tz_localize("UTC").dt.normalize()

        transfers_dfs.append(transfers_report)
        balances_dfs.append(balances_report)

    transfers = TransfersReport.model_validate(pd.concat(transfers_dfs).to_dict(orient="records"))
    balances = BalancesReport.model_validate(pd.concat(balances_dfs).to_dict(orient="records"))

    # tvl_apy
    tvl_apy_df = await get_tvl_apy()
    tvl_apy_report = TVLAPYReport.model_validate(tvl_apy_df.to_dict(orient="records"))

    prices = await get_mean_price_for_symbols_per_month(symbols, balance_target_date)
    daily_prices = await get_daily_prices_for_symbols_per_month(symbols, balance_target_date)

    response = ReportResponse(
        transfers=transfers,
        balances=balances,
        tvl_apy=tvl_apy_report,
        prices=prices,
        daily_prices=daily_prices,
    )
    logger.debug(response)
    return response
