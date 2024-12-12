from datetime import UTC, datetime
from typing import TypedDict

import pandas as pd
from dateutil.utils import today
from httpx import HTTPStatusError, QueryParams
from loguru import logger

from src.core.const import Side
from src.core.dto import JettonAddressBook, Token, Wallet
from src.core.http import send_request
from src.modules.prices.services.coinmarketcap import get_mean_price_for_month_from_cmc
from src.modules.transfers.dto import TransfersReport
from src.modules.transfers.services.ton import get_jetton_transfers

__all__ = ("_get_current_jetton_balances",)

TONCENTER_API_URL = "https://toncenter.com/api/v3"


class JettonBalance(TypedDict):
    owner: Wallet
    jetton: Token
    balance: float
    decimals: int
    usd_price: float


async def _get_current_jetton_balances(wallet: Wallet, jettons: JettonAddressBook) -> list[JettonBalance]:
    """current jetton balances using tonapi"""
    url = f"https://tonapi.io/v2/accounts/{wallet.address}/jettons"
    params = QueryParams(currencies="usd")
    response = await send_request(method="GET", url=url, params=params)
    balances: list[JettonBalance] = []
    for balance in response.json()["balances"]:
        if jetton := jettons.get(balance["jetton"]["address"]):
            balances.append(
                {
                    "owner": wallet,
                    "jetton": jetton,
                    "balance": float(balance["balance"]),
                    "decimals": int(balance["jetton"]["decimals"]),
                    "usd_price": float(balance["price"]["prices"]["USD"]),
                }
            )

    return balances


async def get_jetton_balance(
    wallet: Wallet,
    jettons: JettonAddressBook,
    target_date: datetime | None = None,
) -> pd.DataFrame:
    current_balances = await _get_current_jetton_balances(wallet, jettons)

    if not target_date or target_date.date() == today(UTC).date():
        jetton_balances = await _handle_with_no_target_date(wallet, current_balances)
        return pd.DataFrame(jetton_balances)

    jetton_balances = await _handle_with_target_date(wallet, jettons, current_balances, target_date)
    return pd.DataFrame(jetton_balances)


class _JettonBalances(TypedDict):
    date: datetime
    account_name: str
    symbol: str
    balance_token: float
    balance_usd: float


async def _handle_with_no_target_date(wallet: Wallet, jetton_balances: list[JettonBalance]) -> list[_JettonBalances]:
    date_ = today(UTC)
    result: list[_JettonBalances] = []
    for jetton_balance in jetton_balances:
        jetton = jetton_balance["jetton"]
        balance_token = jetton_balance["balance"] / 10 ** jetton_balance["decimals"]
        balance_usd = jetton_balance["usd_price"] * balance_token
        result.append(
            {
                "date": date_,
                "account_name": wallet.account_name,
                "symbol": jetton.symbol,
                "balance_token": balance_token,
                "balance_usd": balance_usd,
            }
        )

    return result


async def _handle_with_target_date(
    wallet: Wallet,
    jettons: JettonAddressBook,
    jetton_balances: list[JettonBalance],
    target_date: datetime,
) -> list[_JettonBalances]:
    balance_changes: dict[str, float] = {}
    transactions_df = await get_jetton_transfers(wallet, jettons, target_date, today(UTC))
    transactions_df["network"] = "TON"
    transactions = TransfersReport.model_validate(transactions_df.to_dict(orient="records"))
    for transaction in transactions.root[::-1]:
        if transaction.symbol not in balance_changes:
            balance_changes[transaction.symbol] = 0.0

        if transaction.side == Side.IN:
            logger.debug(f"{transaction.symbol}: {balance_changes[transaction.symbol]} += {transaction.value}")
            balance_changes[transaction.symbol] += transaction.value
        else:
            logger.debug(f"{transaction.symbol}: {balance_changes[transaction.symbol]} -= {transaction.value}")
            balance_changes[transaction.symbol] -= transaction.value

    result: list[_JettonBalances] = []
    for jetton_balance in jetton_balances:

        jetton = jetton_balance["jetton"]
        balance_token = (jetton_balance["balance"] / 10 ** jetton_balance["decimals"]) - balance_changes.get(
            jetton.symbol, 0
        )
        try:
            price = await get_mean_price_for_month_from_cmc(jetton.symbol, target_date)
            balance_usd = price.price_end_usd * balance_token if price else 0
        except HTTPStatusError as exc:
            logger.warning(exc)
            balance_usd = jetton_balance["usd_price"] * balance_token

        result.append(
            {
                "date": target_date,
                "account_name": wallet.account_name,
                "symbol": jetton.symbol,
                "balance_token": balance_token,
                "balance_usd": balance_usd,
            }
        )

    return result
