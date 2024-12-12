from asyncio import sleep
from collections.abc import AsyncGenerator, Generator, Iterable
from datetime import datetime
from typing import cast

import pandas as pd
from dateutil.relativedelta import relativedelta
from loguru import logger
from pytoniq import (
    BlockIdExt,
    LiteBalancer,
    LiteClientError,
    LiteClientLike,
    LiteServerError,
)

from src.config import settings
from src.core.utils import get_config


async def _get_block(client: LiteClientLike, date_: datetime) -> BlockIdExt:
    ts = int(date_.timestamp())
    while True:
        try:
            blk, _ = await client.lookup_block(wc=-1, shard=-(2**63), utime=ts, only_archive=True)
        except (LiteServerError, LiteClientError):
            logger.debug(f"failed to get block for {date_} try again in 2 seconds")
            await sleep(2)
        else:
            return blk


async def _get_stton_rate_for_block(client: LiteClientLike, block: BlockIdExt) -> float:
    while True:
        try:
            result = await client.run_get_method(
                address=settings.STTON_ADDRESS,
                method="get_full_data",
                stack=[],
                block=block,
            )
        except (LiteServerError, LiteClientError):
            logger.debug(f"failed to get block for {block} try again in 2 seconds")
            await sleep(2)
        else:
            return cast(float, result[1] / result[0])


async def get_stton_historical_prices(dates: Iterable[datetime]) -> AsyncGenerator[tuple[datetime, float], None]:
    config = get_config()
    async with LiteBalancer.from_config(config, trust_level=2) as client:
        logger.debug("started balancer client")
        for date_ in dates:
            logger.debug(f"Processing date: {date_}")
            block = await _get_block(client, date_)
            rate = await _get_stton_rate_for_block(client, block)
            yield date_, rate


def date_range(
    end_date: datetime,
    amount: int = 12,
    step: relativedelta | None = None,
) -> Generator[datetime, None, None]:
    """
    end_date: the end date of the range
    amount: the amount of dates to generate
    step: the time delta between each date, by default 1 month
    example:
    ```python
    dates = date_range(datetime(2020, 1, 1), 12)
    assert list(dates) == [datetime(2020, 12, 31), datetime(2020, 11, 30), ..., datetime(2020, 1, 31)]
    ```
    """
    if not step:
        step = relativedelta(months=1)

    current_date = end_date
    while amount > 0:
        yield current_date
        current_date = current_date - step
        amount -= 1


async def get_staking_apy(dates: list[datetime]) -> pd.DataFrame:
    stton_prices = []
    async for date_, stton_price in get_stton_historical_prices(dates):
        stton_prices.append({"date": date_, "stTON_price": stton_price})

    stton_prices_df: pd.DataFrame = pd.DataFrame(stton_prices)

    # Calculate staking gross data
    stton_prices_df["month"] = stton_prices_df["date"].dt.strftime("%Y-%m")
    staking_apy = stton_prices_df.groupby("month").apply(lambda x: x.iloc[-1]).reset_index(drop=True)
    staking_apy["rate"] = (
        staking_apy["stTON_price"]
        / staking_apy["stTON_price"].shift(
            fill_value=staking_apy["stTON_price"].iloc[0],
        )
        - 1
    )
    staking_apy["apy_net"] = (staking_apy["rate"] + 1) ** 12 - 1
    staking_apy["apy_gross"] = (staking_apy["rate"] / 0.8 + 1) ** 12 - 1
    return staking_apy[["month", "date", "stTON_price", "rate", "apy_net", "apy_gross"]]
