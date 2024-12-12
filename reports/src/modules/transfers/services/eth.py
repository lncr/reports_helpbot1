from datetime import datetime
from typing import Literal

import pandas as pd
from httpx import QueryParams

from src.config import settings
from src.core.const import Network, Side
from src.core.dto import Wallet
from src.core.http import send_request
from src.modules.transfers.dto import ETHTransfersList

__all__ = ("get_eth_wallet_token_transfers",)

TOKEN_LIST_ETH = pd.read_csv(settings.TOKEN_LIST_ETH_CSV)
ADDRESS_BOOK_ETH = pd.read_csv(settings.ADDRESS_BOOK_ETH_CSV)
ADDRESS_BOOK_ETH["address"] = ADDRESS_BOOK_ETH["address"].str.lower()


async def get_eth_wallet_token_transfers(
    wallet: Wallet,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    params = QueryParams(
        module="account",
        action="tokentx",
        address=wallet.address,
        startblock=await get_block_by_timestamp(start_date, "after"),
        endblock=await get_block_by_timestamp(end_date, "before"),
        sort="asc",
        apikey=settings.ETHERSCAN_API_KEY,
    )
    response = await send_request("GET", settings.ETHERSCAN_API_BASE_URL, params)
    data = ETHTransfersList.model_validate(response.json()["result"])
    return _parse_token_transfers(data, wallet)


def _parse_token_transfers(data: ETHTransfersList, wallet: Wallet) -> pd.DataFrame:
    if not (transfers := data.model_dump(by_alias=True)):
        return pd.DataFrame(columns=["time", "side", "value", "symbol", "address", "account_name"])

    token_transfers = pd.DataFrame(transfers)
    token_transfers["time"] = pd.to_datetime(token_transfers["timeStamp"].astype(int), unit="s", utc=True)
    token_transfers["value"] = token_transfers["value"].astype(float) / (
        10 ** token_transfers["tokenDecimal"].astype(int)
    )
    token_transfers[["side", "address"]] = token_transfers.apply(
        lambda x: pd.Series((Side.IN, x["from"]) if x["to"].lower() == wallet.address.lower() else (Side.OUT, x["to"])),
        axis=1,
    )
    filtered_transfers = token_transfers[token_transfers["contractAddress"].isin(TOKEN_LIST_ETH["contractAddress"])]
    merged_transfers = filtered_transfers.merge(ADDRESS_BOOK_ETH, on="address", how="left")
    final_transfers = merged_transfers[["time", "from", "to", "tokenSymbol", "value", "side", "note", "address"]]
    final_transfers["account_name"] = wallet.account_name
    final_transfers["network"] = Network.ETH
    return final_transfers.rename(columns={"tokenSymbol": "symbol"}).fillna("")


async def get_block_by_timestamp(date: datetime, closest: Literal["before", "after"]) -> int:
    params = QueryParams(
        module="block",
        action="getblocknobytime",
        timestamp=int(date.timestamp()),
        closest=closest,
        apikey=settings.ETHERSCAN_API_KEY,
    )
    response = await send_request(method="GET", url=settings.ETHERSCAN_API_BASE_URL, params=params)
    return int(response.json()["result"])
