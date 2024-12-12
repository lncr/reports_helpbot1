import datetime
from typing import TypedDict

Symbol = str


class Rates(TypedDict):
    rates: dict[Symbol, float]
    date: datetime.date
