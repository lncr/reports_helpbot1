from datetime import UTC, datetime

import pandas as pd
from httpx import QueryParams

from src.config import settings
from src.core.dto import Wallet
from src.core.http import send_request
from src.modules.balances.services.historical.eth import get_historical_eth_balance
from src.modules.prices.services.coinmarketcap import get_mean_price_for_month_from_cmc
from src.modules.prices.services.utils import convert_currency

__all__ = ("get_eth_wallet_balance",)

TOKEN_LIST_ETH = pd.read_csv(settings.TOKEN_LIST_ETH_CSV)


async def get_eth_wallet_balance(wallet: Wallet, target_date: datetime | None = None) -> pd.DataFrame:
    token_balances = []
    for _, row in TOKEN_LIST_ETH.iterrows():
        balance_token = await _get_erc20_token_balance(wallet, row["contractAddress"], row["decimal"])
        balance_usd = await convert_currency(value=balance_token, from_=row["symbol"])
        token_balances.append((row["symbol"], balance_token, balance_usd))

    balance_df = pd.DataFrame(token_balances, columns=["symbol", "balance_token", "balance_usd"])
    current_balance_eth = await _get_eth_balance(wallet)
    if not target_date:
        balance_eth = current_balance_eth
        balance_usd = await convert_currency(value=balance_eth, from_="ETH")
    else:
        balance_eth = await get_historical_eth_balance(wallet, current_balance_eth, target_date)
        balance_usd_price = await get_mean_price_for_month_from_cmc("ETH", target_date)
        balance_usd = balance_usd_price.price_end_usd * balance_eth if balance_usd_price else 0

    eth_balance_df = pd.DataFrame([{"symbol": "ETH", "balance_token": balance_eth, "balance_usd": balance_usd}])

    balance = pd.concat([balance_df, eth_balance_df], ignore_index=True)
    balance["account_name"] = wallet.account_name
    balance["date"] = target_date.date() if target_date else datetime.now(UTC).date()

    return balance[["date", "symbol", "balance_token", "balance_usd", "account_name"]]


async def _get_erc20_token_balance(
    wallet: Wallet,
    token_contract_address: str,
    token_decimal: int,
) -> float:
    params = QueryParams(
        module="account",
        action="tokenbalance",
        contractaddress=token_contract_address,
        address=wallet.address,
        tag="latest",
        apikey=settings.ETHERSCAN_API_KEY,
    )
    response = await send_request(
        method="GET",
        url=settings.ETHERSCAN_API_BASE_URL,
        params=params,
    )
    if response.json()["status"] != "1":
        raise Exception(response.json()["message"])

    balance = float(response.json()["result"])
    return float(balance / (10**token_decimal))


async def _get_eth_balance(wallet: Wallet) -> float:
    params = QueryParams(
        module="account",
        action="balance",
        address=wallet.address,
        tag="latest",
        apikey=settings.ETHERSCAN_API_KEY,
    )
    response = await send_request(
        method="GET",
        url=settings.ETHERSCAN_API_BASE_URL,
        params=params,
    )
    return float(response.json()["result"]) / 1e18
