import pandas as pd

from src.core.utils import get_last_days_of_months_from_now

from .apy import get_staking_apy
from .tvl import get_staking_tvl


async def get_tvl_apy() -> pd.DataFrame:
    dates = get_last_days_of_months_from_now(12)
    start_date = dates[-1]
    end_date = dates[0]

    staking_apy = await get_staking_apy(dates)
    staking_tvl = await get_staking_tvl(protocol="bemo", start_date=start_date, end_date=end_date)

    # Merge staking_apy and staking_tvl data
    result = pd.merge(
        staking_apy,
        staking_tvl[["month", "TVL TON", "TVL USD"]],
        on="month",
        how="left",
    )
    result["date"] = result["date"].dt.date
    return result[["date", "stTON_price", "rate", "apy_net", "apy_gross", "TVL TON", "TVL USD"]].rename(
        columns={
            "stTON_price": "stton_price",
            "TVL TON": "tvl_ton",
            "TVL USD": "tvl_usd",
        }
    )
