from datetime import datetime
from typing import Annotated, Literal, cast

import pandas as pd
from httpx import Headers, QueryParams
from loguru import logger
from typing_extensions import Doc

from src.config import settings
from src.core.http import send_request
from src.modules.prices.dto import DailyPrice, DailyPrices, Price, Prices
from src.modules.prices.services.utils import (
    get_fiat_daily_prices_for_month,
    get_fiat_mean_price_for_month,
)

_TPOINTS = dict[
    Annotated[str, Doc("timestamp")],
    dict[Literal["v"], Annotated[list[int], Doc("list of prices, first one is token price in USD")]],
]


async def get_mean_price_for_symbols_per_month(symbols: list[str], target_date: datetime | None = None) -> Prices:
    prices = Prices([])
    data: list[Price] = prices.root

    if not symbols:
        return prices

    for symbol in symbols:
        price = await get_mean_price_for_month_from_cmc(symbol, target_date)
        if price is None:
            continue
        data.append(price)
        logger.info(price)

    if not data:
        return prices

    logger.debug(f"Fetch fiat price for date {data[0].date}")
    fiat_prices = await get_fiat_mean_price_for_month(data[0].date, to=["EUR", "RUB"], revers=True)
    eur = Price(
        symbol="EUR",
        date=data[0].date,
        price_end_usd=fiat_prices["EUR"]["end"],
        price_mean_usd=fiat_prices["EUR"]["mean"],
    )
    rub = Price(
        symbol="RUB",
        date=data[0].date,
        price_end_usd=fiat_prices["RUB"]["end"],
        price_mean_usd=fiat_prices["RUB"]["mean"],
    )
    data.append(eur)
    data.append(rub)
    return prices


async def get_daily_prices_for_symbols_per_month(
    symbols: list[str], target_date: datetime | None = None
) -> DailyPrices:
    prices = DailyPrices([])
    data: list[DailyPrice] = prices.root

    if not symbols:
        return prices

    for symbol in symbols:
        prices_ = await get_daily_prices_for_month_from_cmc(symbol, target_date)
        data.extend(prices_)
        logger.info(prices_)

    logger.debug(f"Fetch fiat daily prices for month {data[0].date:%Y-%m}")
    fiat_prices = await get_fiat_daily_prices_for_month(data[0].date, to=["EUR", "RUB"], revers=True)
    for symbol in fiat_prices:
        data.extend(fiat_prices[symbol])

    return prices


async def get_mean_price_for_month_from_cmc(token_symbol: str, target_date: datetime | None = None) -> Price | None:
    price_list = await _get_price_list_from_cmc(token_symbol, target_date)
    if price_list.empty:
        return None

    price_mean_usd = price_list["price"].mean()
    end_row = price_list.iloc[-1]
    return Price(
        symbol=token_symbol,
        date=end_row["date"],
        price_end_usd=end_row["price"],
        price_mean_usd=price_mean_usd,
    )


async def get_daily_prices_for_month_from_cmc(
    token_symbol: str,
    target_date: datetime | None = None,
) -> list[DailyPrice]:
    price_list = await _get_price_list_from_cmc(token_symbol, target_date)
    price_list = price_list.groupby("date", as_index=False).agg({"price": "mean"})

    result: list[DailyPrice] = []
    for record in price_list.to_dict(orient="records"):
        result.append(
            DailyPrice(
                symbol=token_symbol,
                date=record["date"],
                price=record["price"],
            )
        )
    return result


async def _get_price_list_from_cmc(token_symbol: str, target_date: datetime | None = None) -> pd.DataFrame:
    points = await _fetch_price_points_from_cmc(token_symbol, target_date)
    price_list = _create_price_list(points)
    if target_date:
        price_list = await _filter_prices_by_target_date(price_list, target_date)

    return price_list


async def _fetch_price_points_from_cmc(token_symbol: str, target_date: datetime | None = None) -> _TPOINTS:
    token_id = await _get_id_of_token_for_cmc(token_symbol)
    response = await send_request(
        method="GET",
        url="https://api.coinmarketcap.com/data-api/v3/cryptocurrency/detail/chart",
        params=QueryParams(id=token_id, range="1Y" if target_date else "1M"),
    )
    return cast(_TPOINTS, response.json()["data"]["points"])


async def _filter_prices_by_target_date(price_list: pd.DataFrame, target_date: datetime) -> pd.DataFrame:
    return price_list[
        (price_list["date"] >= target_date.date().replace(day=1)) & (price_list["date"] <= target_date.date())
    ]


def _create_price_list(data: _TPOINTS) -> pd.DataFrame:
    price_list = pd.DataFrame(
        [{"timestamp": int(timestamp), "price": point["v"][0]} for timestamp, point in data.items()]
    )
    price_list["date"] = pd.to_datetime(price_list["timestamp"], unit="s").dt.date
    price_list["month"] = price_list["date"].apply(lambda x: f"{x.year}-{x.month:02}")
    price_list = price_list[["date", "month", "price"]]

    return price_list


async def _get_id_of_token_for_cmc(symbol: str) -> int:
    response = await send_request(
        method="GET",
        url="https://pro-api.coinmarketcap.com/v2/cryptocurrency/info",
        params=QueryParams(symbol=symbol),
        headers=Headers({"X-CMC_PRO_API_KEY": str(settings.CMC_API_KEY)}),
        no_retries=True,
    )
    return cast(int, response.json()["data"][symbol.upper()][0]["id"])
