import datetime

from pydantic import RootModel

from src.core.dto import BaseDTO


class Price(BaseDTO):
    symbol: str
    date: datetime.date
    price_end_usd: float
    price_mean_usd: float


class Prices(RootModel[list[Price]]): ...


class DailyPrice(BaseDTO):
    symbol: str
    date: datetime.date
    price: float


class DailyPrices(RootModel[list[DailyPrice]]): ...


class PricesReport(BaseDTO):
    prices: Prices
    daily_prices: DailyPrices
