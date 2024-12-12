import datetime

from pydantic import RootModel

from src.core.dto import BaseDTO


class Balance(BaseDTO):
    date: datetime.date
    symbol: str
    balance_token: float
    balance_usd: float
    account_name: str


class BalancesReport(RootModel[list[Balance]]): ...
