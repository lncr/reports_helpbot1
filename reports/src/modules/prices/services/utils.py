from calendar import monthrange
from collections import defaultdict
from datetime import UTC, date
from typing import TypedDict

import pandas as pd
from dateutil.utils import today
from httpx import QueryParams
from loguru import logger

from src.config import settings
from src.core.http import send_request
from src.modules.prices.dto import DailyPrice
from src.modules.prices.services.types import Rates, Symbol

CONVERTER_API_URL = "https://api.coinconvert.net/convert"


async def convert_currency(value: float, from_: str, to: str = "USD") -> float:
    if not value:
        return 0.0

    if from_ == to:
        logger.warning(f"Same currency `{from_}`, no reason to convert")
        return value

    response = await send_request(
        method="GET",
        url=f"{CONVERTER_API_URL}/{from_.lower()}/{to.lower()}?amount={value}",
    )
    logger.debug(f"Converted {from_.upper()} to {to.upper()}: {response.json()}")
    return float(response.json()[to.upper()])


class FiatPrice(TypedDict):
    mean: float
    end: float


async def get_fiat_mean_price_for_month(
    month_date: date, to: str | list[str], revers: bool = False
) -> dict[Symbol, FiatPrice]:
    rate_list = await _get_rates_for_every_day_of_month(month_date, to)
    result = _calculate_mean_prices(rate_list)
    if revers:
        return {
            symbol: {"mean": 1 / value, "end": 1 / rate_list[-1]["rates"][symbol]} for symbol, value in result.items()
        }
    return {symbol: {"mean": value, "end": rate_list[-1]["rates"][symbol]} for symbol, value in result.items()}


async def get_fiat_daily_prices_for_month(
    month_date: date, to: str | list[str], revers: bool = False
) -> dict[Symbol, list[DailyPrice]]:
    rate_list = await _get_rates_for_every_day_of_month(month_date, to)
    result = _calculate_daily_prices(rate_list)
    if revers:
        return {
            symbol: [
                DailyPrice(symbol=symbol, date=daily_price.date, price=1 / daily_price.price)
                for daily_price in daily_prices
            ]
            for symbol, daily_prices in result.items()
        }

    return result


async def _get_rates_for_every_day_of_month(month_date: date, to: str | list[str]) -> list[Rates]:
    """Supports only USD base currency"""
    rates: list[Rates] = []

    now = today(UTC)
    latest_rates: Rates | None = None
    if now.month == month_date.month and now.year == month_date.year:
        end_of_month = now.day - 1
        today_usd_balances: dict[Symbol, float] = {}
        for from_ in to:
            balance_usd = await convert_currency(value=1, from_=from_)
            today_usd_balances[from_.upper()] = 1 / balance_usd

        latest_rates = Rates(date=now.date(), rates=today_usd_balances)

        if end_of_month < 1:
            return [latest_rates]

    else:
        end_of_month = monthrange(month_date.year, month_date.month)[1]

    existing_df = _load_rates()
    if not existing_df.empty:
        logger.debug(f"month: {month_date}, end_of_month: {end_of_month}")
        filtered_df = existing_df[
            (pd.to_datetime(existing_df["date"], format="%Y-%m-%d").dt.date >= month_date.replace(day=1))
            & (pd.to_datetime(existing_df["date"], format="%Y-%m-%d").dt.date <= month_date.replace(day=end_of_month))
        ]
        if not filtered_df.empty:
            rates = _unpivot_dataframe(filtered_df)

    if latest_rates:
        rates.append(latest_rates)
    if rates and len(rates) == end_of_month:
        logger.debug("returning existing rates")
        return rates

    logger.debug("gonna fetch new rates")
    url = "https://openexchangerates.org/api/historical/{date:%Y-%m-%d}.json"
    params = QueryParams(
        app_id=settings.OPEN_EXCHANGE_RATE_API_ID,
        symbols=to.lower() if isinstance(to, str) else ",".join(map(str.lower, to)),
        show_alternative=False,
        prettyprint=False,
    )

    for day in range(1, end_of_month + 1):
        # if rates and day in [date.fromisoformat(rate["date"]).day for rate in rates]:
        if rates and day in [rate["date"].day for rate in rates]:
            continue

        date_ = month_date.replace(day=day)
        logger.debug(date_)
        response = await send_request(
            method="GET",
            url=url.format(date=date_),
            params=params,
        )
        rates.append(Rates(date=date_, rates=response.json()["rates"]))

    logger.debug("saving new rates")
    _save_rates(rates, existing_df)

    return rates


def _calculate_mean_prices(rates_list: list[Rates]) -> dict[Symbol, float]:
    # Initialize dictionaries to store the sum of rates and the count of occurrences for each symbol
    sum_rates: dict[str, float] = defaultdict(float)
    count_rates: dict[str, int] = defaultdict(int)

    # Iterate through each Rates object in the list
    for rates_obj in rates_list:
        rates = rates_obj["rates"]
        for symbol, rate in rates.items():
            sum_rates[symbol] += rate
            count_rates[symbol] += 1

    # Calculate the mean price for each symbol
    mean_prices: dict[Symbol, float] = {symbol: sum_rates[symbol] / count_rates[symbol] for symbol in sum_rates}
    return mean_prices


def _calculate_daily_prices(rates_list: list[Rates]) -> dict[Symbol, list[DailyPrice]]:
    result: dict[Symbol, list[DailyPrice]] = {}

    # Iterate through each Rates object in the list
    for rates_obj in rates_list:
        rates = rates_obj["rates"]
        for symbol, rate in rates.items():
            if symbol in result:
                result[symbol].append(DailyPrice(symbol=symbol, date=rates_obj["date"], price=rate))
            else:
                result[symbol] = [DailyPrice(symbol=symbol, date=rates_obj["date"], price=rate)]

    return result


def _save_rates(rates: list[Rates], existing_df: pd.DataFrame | None = None) -> None:
    if existing_df is None:
        existing_df = _load_rates()

    new_df = _flatten_rates(rates)
    df = _pivot_dataframe(new_df)
    df = _concatenate_rates_dataframes(existing_df, df)
    df.to_csv(settings.OPEN_EXCHANGE_RATE_DATA, index=False)


def _load_rates() -> pd.DataFrame:
    with settings.OPEN_EXCHANGE_RATE_DATA.open() as file:
        df = pd.read_csv(file)
    logger.debug(f"loaded rates: {df}")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d").dt.date
    return df


def _flatten_rates(rates: list[Rates]) -> pd.DataFrame:
    """Flatten the dictionary structure."""
    flattened_data = []
    for entry in rates:
        date = entry["date"]
        for currency, rate in entry["rates"].items():
            flattened_data.append({"date": date, "currency": currency, "rate": rate})
    return pd.DataFrame(flattened_data)


def _concatenate_rates_dataframes(existing_df: pd.DataFrame, new_df: pd.DataFrame) -> pd.DataFrame:
    """Concatenate existing and new DataFrames, removing duplicates."""
    combined_df = pd.concat([existing_df, new_df])
    combined_df = combined_df.drop_duplicates(subset=["date"])
    return combined_df


def _pivot_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot the DataFrame to get the desired format."""
    return df.pivot(index="date", columns="currency", values="rate").reset_index()


def _unpivot_dataframe(df: pd.DataFrame) -> list[Rates]:
    """Convert the pivoted DataFrame back to the original dictionary structure."""
    df_melted = df.melt(id_vars=["date"], var_name="currency", value_name="rate")
    grouped = df_melted.groupby("date")
    rates_list: list[Rates] = []
    for date_, group in grouped:
        rates_dict: Rates = {
            "date": date.fromisoformat(str(date_)),
            "rates": group.set_index("currency")["rate"].to_dict(),
        }
        rates_list.append(rates_dict)

    return rates_list
