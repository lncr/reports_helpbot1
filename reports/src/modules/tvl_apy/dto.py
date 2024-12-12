import datetime

from pydantic import RootModel

from src.core.dto import BaseDTO


class TVLAPY(BaseDTO):
    date: datetime.date
    apy_net: float
    apy_gross: float
    tvl_ton: float
    tvl_usd: float
    stton_price: float
    rate: float


class TVLAPYReport(RootModel[list[TVLAPY]]): ...
