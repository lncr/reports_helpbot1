from datetime import datetime

import pandas as pd
from loguru import logger
from pytoniq import LiteClientError, LiteServerError

from src.config import settings
from src.core.const import DTON_URL, Network, Side
from src.core.dto import JettonAddressBook, JettonTransactionList, Wallet
from src.core.http import send_request
from src.core.utils import get_jetton_wallets
from src.modules.transfers.dto import DTONQuery, TONTransfersList
from src.modules.transfers.services.const import BEMO_ADDRESS
from src.modules.transfers.services.jettons import fetch_jetton_transfers

__all__ = ("get_ton_transfers",)

TONCENTER_API_URL = "https://toncenter.com/api/v3"
ADDRESS_BOOK_TON = pd.read_csv(settings.ADDRESS_BOOK_TON_CSV)


async def get_ton_transfers(
    wallet: Wallet, jettons: JettonAddressBook, start_date: datetime, end_date: datetime
) -> pd.DataFrame:
    ton_transfers = await _get_ton_transfers(wallet=wallet, start_date=start_date, end_date=end_date)
    jetton_transfers = await get_jetton_transfers(
        wallet=wallet,
        jettons=jettons,
        start_date=start_date,
        end_date=end_date,
    )
    transfers = pd.concat([ton_transfers, jetton_transfers], ignore_index=True)
    transfers["network"] = Network.TON
    transfers = transfers.sort_values(by=["account_name", "time"])
    transfers = _remove_duplicates(transfers)
    return transfers


def _remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    df["intvalue"] = df["value"].astype(int)
    # Group by relevant columns
    grouped = df.groupby(["time", "account_name", "intvalue"], group_keys=False)
    df_cleaned = grouped.apply(_process_group_with_duplicates).reset_index(drop=True)
    return df_cleaned.drop(columns=["intvalue"])


def _process_group_with_duplicates(group: pd.DataFrame) -> pd.Series:  # type: ignore
    if len(group) > 1:
        # Check for a row with Note starting with "Swapping"
        swapping_note = group[group["note"].str.startswith("Swapping")]
        if not swapping_note.empty:
            # Update the Note and keep the original Value with fractional part
            original_value_row = group.iloc[0]
            swapping_note_row = swapping_note.iloc[0]
            original_value_row["note"] = swapping_note_row["note"]
            return original_value_row
        return group.iloc[0]
    return group.iloc[0]


async def _get_ton_transfers(
    wallet: Wallet,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    data = {
        "query": f"""{{
            raw_transactions(
                address_friendly: "{wallet.address}"
                gen_utime__gte: "{start_date.strftime("%Y-%m-%dT%H:%M:%S")}"
                gen_utime__lte: "{end_date.strftime("%Y-%m-%dT%H:%M:%S")}"
            ){{
                gen_utime
                account_storage_balance_grams
                in_msg_value_grams
                out_msg_value_grams
                out_msg_dest_addr_address_hex
                in_msg_src_addr_address_hex
                in_msg_comment
                compute_ph_gas_fees
                compute_ph_gas_used
                compute_ph_gas_limit
                action_ph_total_fwd_fees
                action_ph_total_action_fees
                storage_ph_storage_fees_collected
                storage_ph_storage_fees_due
                in_msg_fwd_fee_grams
                in_msg_ihr_fee_grams
                out_msg_fwd_fee_grams
                out_msg_ihr_fee_grams
            }}
        }}"""
    }
    validated_data = DTONQuery.model_validate(data)
    response = await send_request(method="POST", url=DTON_URL, data=validated_data)
    ton_transfers = TONTransfersList.model_validate(response.json()["data"]["raw_transactions"])
    result = _parse_ton_transfers(data=ton_transfers, wallet=wallet)
    return result


async def get_jetton_transfers(
    wallet: Wallet,
    jettons: JettonAddressBook,
    start_date: datetime,
    end_date: datetime,
) -> pd.DataFrame:
    while True:
        try:
            jetton_wallets = await get_jetton_wallets(wallet, jettons)
        except (LiteServerError, LiteClientError):
            logger.warning("lite server doesnt respond while getting jetton wallets")
            continue

        break

    all_transfers = JettonTransactionList([])
    for jetton_wallet in jetton_wallets:
        transfers = await fetch_jetton_transfers(jetton_wallet, start_date, end_date)
        all_transfers.root.extend(transfers)

    return _parse_jetton_transfers(data=all_transfers)


def _parse_ton_transfers(data: TONTransfersList, wallet: Wallet) -> pd.DataFrame:
    if not (transfers := data.model_dump()):
        return pd.DataFrame(columns=["date", "time", "side", "value", "symbol", "address", "account_name"])

    transfers_dt = pd.DataFrame(transfers)

    # NOTE: bcs of DTON there is not a UTC time, there is ACTUALLY moscow time...
    # transfers_dt["time"] = pd.to_datetime(transfers_dt["gen_utime"], utc=True)
    transfers_dt["time"] = pd.to_datetime(transfers_dt["gen_utime"])
    transfers_dt["time"] = transfers_dt["time"].dt.tz_localize("Europe/Moscow")
    transfers_dt["time"] = transfers_dt["time"].dt.tz_convert("UTC")

    transfers_dt["date"] = transfers_dt["time"].dt.date
    transfers_dt["in_msg_value_grams"] = transfers_dt["in_msg_value_grams"].astype(float) / 1e9
    transfers_dt["out_msg_value_grams"] = transfers_dt["out_msg_value_grams"].apply(_clean_out_msg_value)
    transfers_dt["out_msg_value_grams"] = transfers_dt["out_msg_value_grams"].astype(float) / 1e9
    transfers_dt["account_storage_balance_grams"] = transfers_dt["account_storage_balance_grams"].astype(float) / 1e9
    transfers_dt["side"] = transfers_dt.apply(
        lambda x: Side.OUT if pd.isna(x["in_msg_value_grams"]) else Side.IN, axis=1
    )
    transfers_dt["value"] = transfers_dt.apply(
        lambda x: x["out_msg_value_grams"] if pd.isna(x["in_msg_value_grams"]) else x["in_msg_value_grams"], axis=1
    )
    transfers_dt["symbol"] = Network.TON
    transfers_dt["address"] = transfers_dt.apply(
        lambda x: (
            _clean_out_msg_value(x["out_msg_dest_addr_address_hex"])
            if pd.isna(x["in_msg_src_addr_address_hex"])
            else x["in_msg_src_addr_address_hex"]
        ),
        axis=1,
    )
    transfers_dt = transfers_dt.merge(ADDRESS_BOOK_TON, left_on="address", right_on="address", how="left")
    transfers_dt["note"] = transfers_dt.apply(
        lambda x: (
            "protocol fee"
            if x["in_msg_comment"] == "протокол"
            else ("validator fee" if x["in_msg_comment"] == "val" else x["in_msg_comment"])
        ),
        axis=1,
    )
    transfers_dt["address"] = transfers_dt["address"].apply(lambda x: f"0:{x.lower()}")
    transfers_dt["note"] = transfers_dt.apply(
        lambda x: ("bemo staking" if x["address"] == BEMO_ADDRESS else x["note"]),
        axis=1,
    )
    transfers_dt.loc[transfers_dt["value"] < 0.5, "note"] = "transaction fee"
    transfers_dt["account_name"] = wallet.account_name
    transfers_dt = transfers_dt.dropna(subset=["value"])
    return transfers_dt[["date", "time", "side", "value", "symbol", "note", "address", "account_name"]].fillna("")


def _parse_jetton_transfers(data: JettonTransactionList) -> pd.DataFrame:
    if not (transfers := data.model_dump()):
        return pd.DataFrame(columns=["date", "time", "side", "value", "symbol", "note", "address", "account_name"])

    transfers_df = pd.DataFrame(transfers)
    transfers_df.rename(columns={"date": "time", "amount": "value"}, inplace=True)
    transfers_df["date"] = transfers_df["time"].dt.date

    return transfers_df[["date", "time", "side", "value", "symbol", "note", "address", "account_name"]]


def _clean_out_msg_value[_T: str | float | int](value: _T | list[_T]) -> _T | None:
    if isinstance(value, list):
        return value[0] if value else None

    return value
