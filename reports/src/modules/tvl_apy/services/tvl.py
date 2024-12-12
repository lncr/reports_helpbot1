from datetime import datetime

import pandas as pd

from src.core.http import send_request


async def get_staking_tvl(*, protocol: str = "bemo", start_date: datetime, end_date: datetime) -> pd.DataFrame:
    tvl = await _get_defilama_tvl(protocol)
    tvl["month"] = tvl["date"].dt.strftime("%Y-%m")
    tvl = tvl.groupby("month").apply(lambda x: x.iloc[-1]).reset_index(drop=True)
    tvl = tvl[(tvl["date"] >= start_date.strftime("%Y-%m-%d")) & (tvl["date"] <= end_date.strftime("%Y-%m-%d"))]
    return tvl[["month", "date", "TVL TON", "TVL USD"]]


async def _get_defilama_tvl(protocol: str) -> pd.DataFrame:
    response = await send_request(method="GET", url=f"https://api.llama.fi/protocol/{protocol}")

    data = response.json()["chainTvls"]["TON"]

    data_ton = pd.DataFrame(data["tokens"])
    data_ton["date"] = pd.to_datetime(data_ton["date"], unit="s")
    data_ton["TVL TON"] = data_ton["tokens"].apply(lambda x: x["TON"])

    data_usd = pd.DataFrame(data["tokensInUsd"])
    data_usd["date"] = pd.to_datetime(data_usd["date"], unit="s")
    data_usd["TVL USD"] = data_usd["tokens"].apply(lambda x: x["TON"])

    return pd.merge(data_ton, data_usd, on="date")
