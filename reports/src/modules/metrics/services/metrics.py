import pandas as pd

from src.core.http import send_request
from src.modules.metrics.services.constants import (
    EXPECTED_DURATION,
    RUN_VALIDATOR_NUMBER,
    SMA_WEEKS,
    TON_PER_VALUE,
)


def sma(series: "pd.Series[float]", window: int) -> "pd.Series[float]":
    """
    Finds Simple Moving Average(SMA) of given series
    """
    return series.rolling(window=window).mean()


async def generate_tvl_metrics() -> pd.DataFrame:

    response = await send_request(method="GET", url="https://api.llama.fi/protocol/bemo")

    data = response.json()["chainTvls"]["TON"]

    tvl_daily = pd.DataFrame(data["tokens"])
    tvl_daily["tokens"] = tvl_daily["tokens"].apply(lambda x: x["TON"])
    tvl_daily["tvl"] = tvl_daily["tokens"].astype(float)
    tvl_daily["date"] = pd.to_datetime(tvl_daily["date"], unit="s")
    tvl_daily["delta"] = tvl_daily["tvl"] - tvl_daily["tvl"].shift(1).fillna(tvl_daily["tvl"].iloc[0])

    tvl_daily["sma_w"] = sma(tvl_daily["delta"], SMA_WEEKS) * 7
    tvl_daily["growth_rate_expected_2w"] = tvl_daily["sma_w"] * EXPECTED_DURATION
    tvl_daily["n_req_validators"] = (tvl_daily["tvl"] // TON_PER_VALUE).astype(int) + 1
    tvl_daily["exp_new_val"] = (tvl_daily["tvl"] % TON_PER_VALUE + tvl_daily["growth_rate_expected_2w"]) / TON_PER_VALUE
    tvl_daily["exp_new_val_adj"] = tvl_daily["exp_new_val"] - (RUN_VALIDATOR_NUMBER - tvl_daily["n_req_validators"])

    tvl_daily = tvl_daily.fillna(0)

    return tvl_daily
