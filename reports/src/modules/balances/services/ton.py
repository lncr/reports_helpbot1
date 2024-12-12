from datetime import UTC, datetime

import pandas as pd
from httpx import QueryParams
from loguru import logger

from src.core.dto import Wallet
from src.core.http import send_request
from src.modules.balances.services.historical.ton import get_historical_ton_balance
from src.modules.prices.services.coinmarketcap import get_mean_price_for_month_from_cmc
from src.modules.prices.services.utils import convert_currency

__all__ = ("get_ton_balance",)

TONCENTER_API_URL = "https://toncenter.com/api/v3"


async def get_ton_balance(wallet: Wallet, target_date: datetime | None = None) -> pd.DataFrame:
    current_balance = await get_current_ton_balance(wallet)
    if not target_date:
        balance_token = current_balance
        balance_usd = await convert_currency(balance_token, "TON", "USD")
    else:
        balance_token = await get_historical_ton_balance(wallet, target_date, current_balance)
        logger.debug(balance_token)
        balance_usd_price = await get_mean_price_for_month_from_cmc("TON", target_date)
        balance_usd = balance_usd_price.price_end_usd * balance_token if balance_usd_price else 0
        logger.debug(balance_usd)

    return pd.DataFrame(
        [
            {
                "date": target_date.date() if target_date else datetime.now(UTC).date(),
                "symbol": "TON",
                "balance_token": balance_token,
                "balance_usd": balance_usd,
                "account_name": wallet.account_name,
            }
        ]
    )


async def get_current_ton_balance(wallet: Wallet) -> float:
    params = QueryParams(address=wallet.address)
    response = await send_request(
        method="GET",
        url=f"{TONCENTER_API_URL}/account",
        params=params,
        follow_redirects=True,
    )
    return float(response.json()["balance"]) / 1e9
