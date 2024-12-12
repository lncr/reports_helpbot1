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

router = APIRouter(prefix="/balances", tags=["reports"])


@router.post("/")
async def generate_balances_report(
    *,
    wallets: Wallets,
    jettons: JettonAddressBook,
    month: int = Query(ge=1, le=12),
    year: int | None = None,
) -> BalancesReport:
    """Balances report for given wallets and jettons for specified time period"""

    now = today(UTC)
    year = year or now.year
    balance_target_date = None
    if year == now.year and month > now.month:
        month = now.month

    logger.debug(f"Generating report for {month=}")

    _, end_date = get_start_and_end_dates_for_request(month, year)
    if month != now.month or year != now.year:
        balance_target_date = end_date

    balances_dfs: list[pd.DataFrame] = []

    for wallet in wallets.root:
        if get_wallet_network(wallet) is Network.ETH:
            print(1111111111111111111111111111111111111111111111111111111)
            balances_report = await get_eth_wallet_balance(wallet, balance_target_date)
            if not balances_report.empty:
                balances_report["date"] = pd.to_datetime(balances_report["date"], errors="coerce").dt.tz_localize(None)
                balances_report["date"] = balances_report["date"].dt.tz_localize("UTC").dt.normalize()
        else:
            print(2222222222222222222222222222222222222222222222222222222222)
            balances_ton_report = await get_ton_balance(wallet, balance_target_date)
            print(33333333333333333333333333333333333333333333333333333333333)
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

        balances_dfs.append(balances_report)

    return BalancesReport.model_validate(pd.concat(balances_dfs).to_dict(orient="records"))
