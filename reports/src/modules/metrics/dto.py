import datetime

from src.core.dto import BaseDTO


class TVLMetrics(BaseDTO):
    date: datetime.datetime
    tvl: float
    delta: float
    sma_w: float | None = None
    growth_rate_expected_2w: float | None = None
    n_req_validators: int
    exp_new_val: float
    exp_new_val_adj: float
