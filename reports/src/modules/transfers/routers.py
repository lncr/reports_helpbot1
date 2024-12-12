import contextlib
from datetime import UTC

import pandas as pd
from dateutil.utils import today
from fastapi import APIRouter, Query
from loguru import logger

from src.core.const import Network
from src.core.dto import JettonAddressBook, Wallets
from src.core.utils import get_start_and_end_dates_for_request, get_wallet_network
from src.modules.transfers.dto import TransfersReport
from src.modules.transfers.services.eth import get_eth_wallet_token_transfers
from src.modules.transfers.services.ton import get_ton_transfers

router = APIRouter(prefix="/transfers", tags=["reports"])


@router.post("/")
async def generate_transfers_report(
    *,
    wallets: Wallets,
    jettons: JettonAddressBook,
    month: int = Query(ge=1, le=12),
    year: int | None = None,
) -> TransfersReport:
    """Transfers report for given wallets and jettons for specified time period"""
    now = today(UTC)
    year = year or now.year
    if year == now.year and month > now.month:
        month = now.month

    logger.debug(f"Generating report for {month=}")
    start_date, end_date = get_start_and_end_dates_for_request(month, year)
    transfers_dfs: list[pd.DataFrame] = []

    for wallet in wallets.root:
        if get_wallet_network(wallet) is Network.ETH:
            transfers_report = await get_eth_wallet_token_transfers(wallet, start_date, end_date)
        else:
            transfers_report = await get_ton_transfers(wallet, jettons, start_date, end_date)

        if not transfers_report.empty:
            with contextlib.suppress(KeyError):
                transfers_report["date"] = pd.to_datetime(transfers_report["date"]).dt.tz_localize("UTC").dt.normalize()

        transfers_dfs.append(transfers_report)

    return TransfersReport.model_validate(pd.concat(transfers_dfs).to_dict(orient="records"))
