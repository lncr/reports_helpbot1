import json
import re
from calendar import monthrange
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast

import pandas as pd
from dateutil.utils import today
from loguru import logger
from pydantic import Field
from pytoniq import Address, LiteBalancer, begin_cell

from src.config import settings
from src.core.const import Network
from src.core.dto import JettonAddressBook, JettonWallet, Wallet

ETH_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
TON_PATTERN = re.compile(r"^(EQ|Ef|kQ)[0-9A-Za-z_-]{43}$")


def get_config() -> dict[str, Any]:
    with settings.TON_CONFIG.open() as file:
        config = json.load(file)

    return cast(dict[str, Any], config)


def get_last_days_of_months_from_now(number_of_months: int) -> list[datetime]:
    today_datetime = today(UTC)
    last_days = []

    for _ in range(number_of_months):
        last_day = today_datetime.replace(day=1) - timedelta(days=1)
        last_days.append(last_day)
        today_datetime = last_day.replace(day=1)

    return last_days


def get_wallet_network(wallet: Wallet) -> Network:
    if ETH_PATTERN.match(wallet.address):
        return Network.ETH
    return Network.TON


def get_start_and_end_dates_for_request(
    month: Annotated[int, Field(ge=1, le=12)],
    year: int | None = None,
) -> tuple[datetime, datetime]:
    """
    return first and last days for the month.
    if year is not provided, it will return first and last days for the month of the current year
    """
    now = today(UTC)
    if not year:
        year = now.year

    start_date = datetime(year, month, 1, tzinfo=UTC)
    if month == now.month and year == now.year:
        end_date = now
    else:
        end_date = (
            datetime(year, month, monthrange(year, month)[1], tzinfo=UTC) + timedelta(days=1) - timedelta(seconds=1)
        )

    return start_date, end_date


async def get_jetton_wallets(wallet: Wallet, jettons: JettonAddressBook) -> list[JettonWallet]:
    config = get_config()
    jetton_wallets: list[JettonWallet] = []
    async with LiteBalancer.from_config(config, trust_level=2) as provider:
        try:
            user_address = Address(wallet.address)
        except Exception:
            logger.error(f"Failed to parse address {wallet.address}")
            raise

        for jetton in jettons.root:
            address = (
                await provider.run_get_method(
                    address=jetton.address,
                    method="get_wallet_address",
                    stack=[begin_cell().store_address(user_address).end_cell().begin_parse()],
                )
            )[0].load_address()
            raw_address = f"{address.to_tl_account_id()["workchain"]}:{address.to_tl_account_id()["id"]}"
            jetton_wallets.append(
                JettonWallet(
                    address=raw_address,
                    account_name=wallet.account_name,
                    jetton_master=jetton.address,
                    symbol=jetton.symbol,
                )
            )

    return jetton_wallets


def create_media_if_not_exists() -> None:
    if not settings.OPEN_EXCHANGE_RATE_DATA.exists():
        df = pd.DataFrame(columns=["date", "EUR", "RUB"])
        df.to_csv(settings.OPEN_EXCHANGE_RATE_DATA, index=False)
