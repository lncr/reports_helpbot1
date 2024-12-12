import base64
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from loguru import logger
from pytoniq import Cell

from src.core.const import DTON_URL, JettonActionType, Side
from src.core.dto import JettonTransaction, JettonWallet
from src.core.http import send_request
from src.modules.transfers.dto import DTONQuery, DtonTransaction
from src.modules.transfers.services.const import BEMO_ADDRESS, OpCode

DTON_QUERY = """
{{
  raw_transactions(
    {filters}
  ) {{
    {attributes}
  }}
}}
"""

DEFAULT_NOTE = "bemo staking"


async def fetch_bemo_staking_transactions(
    wallet: JettonWallet, start: datetime, end: datetime
) -> list[JettonTransaction]:
    start = start.replace(tzinfo=UTC) + timedelta(hours=3)
    end = end.replace(tzinfo=UTC) + timedelta(hours=3)

    filters = {
        "workchain": 0,
        "gen_utime__gte": int(start.timestamp()),
        "gen_utime__lte": int(end.timestamp()),
    }
    burn_transactions = await _fetch_burns(filters, wallet)
    mint_transactions = await _fetch_mints(filters, wallet)
    return [*burn_transactions, *mint_transactions]


async def _fetch_burns(filters: dict[str, Any], wallet: JettonWallet) -> list[JettonTransaction]:
    account_id = wallet.address.lstrip("0:").upper()
    transactions = await _fetch_transactions_from_dton_with_pagination(
        {
            **filters,
            "in_msg_src_addr_address_hex": account_id,
            # NOTE: could help out with optimization
            "address": BEMO_ADDRESS.lstrip("0:").upper(),
            "in_msg_op_code_hex": OpCode.burn,
        },
        list(DtonTransaction.model_fields),
    )

    result: list[JettonTransaction] = []
    for transaction in transactions:
        if transaction.in_msg_dest_addr_address_hex != BEMO_ADDRESS.lstrip("0:").upper():
            continue
        # NOTE: could help out with optimization
        # if transaction.in_msg_op_code != int(OpCode.burn, 16):
        #     continue
        amount = _parse_jettons_amount(transaction.in_msg_body)
        result.append(
            JettonTransaction(
                date=utcdate_from_dton_gen_utime(transaction.gen_utime),
                symbol="stTON",
                account_name=wallet.account_name,
                type=JettonActionType.Burn,
                side=Side.OUT,
                amount=amount,
                address=BEMO_ADDRESS,
                jetton_master=BEMO_ADDRESS,
                note=DEFAULT_NOTE,
            )
        )

    return result


async def _fetch_mints(filters: dict[str, Any], wallet: JettonWallet) -> list[JettonTransaction]:
    account_id = wallet.address.lstrip("0:").upper()
    transactions = await _fetch_transactions_from_dton_with_pagination(
        {
            **filters,
            # NOTE: could help out with optimization
            # "in_msg_src_addr_address_hex": BEMO_ADDRESS.lstrip("0:").upper(),
            "address": account_id,
            "in_msg_op_code_hex": OpCode.internal_transfer,
        },
        list(DtonTransaction.model_fields),
    )

    result: list[JettonTransaction] = []
    for transaction in transactions:
        if transaction.in_msg_src_addr_address_hex != BEMO_ADDRESS.lstrip("0:").upper():
            continue
        # NOTE: could help out with optimization
        # if transaction.in_msg_op_code != int(OpCode.internal_transfer, 16):
        #     continue
        amount = _parse_jettons_amount(transaction.in_msg_body)
        result.append(
            JettonTransaction(
                date=utcdate_from_dton_gen_utime(transaction.gen_utime),
                symbol="stTON",
                account_name=wallet.account_name,
                type=JettonActionType.Mint,
                side=Side.IN,
                amount=amount,
                address=BEMO_ADDRESS,
                jetton_master=BEMO_ADDRESS,
                note=DEFAULT_NOTE,
            )
        )

    return result


async def _fetch_transactions_from_dton(filters: dict[str, Any], attributes: list[str]) -> list[DtonTransaction]:
    gql_query = DTON_QUERY.format(
        filters="\n".join(
            f'{key}: "{value}"' if key not in ("lt__lt", "workchain") else f"{key}: {value}"
            for key, value in filters.items()
        ),
        attributes="\n".join(attributes),
    )
    logger.debug(gql_query)

    response = await send_request("POST", DTON_URL, data=DTONQuery(query=gql_query))
    data = response.json()["data"]

    response.raise_for_status()

    if errors := data.get("errors"):
        logger.error(f"dton response errors: {errors}")
        return []

    if data["raw_transactions"] is None:
        return []

    return [DtonTransaction.model_validate(transaction) for transaction in data["raw_transactions"]]


async def _fetch_transactions_from_dton_with_pagination(
    filters: dict[str, Any], attributes: list[str]
) -> list[DtonTransaction]:
    transactions: list[DtonTransaction] = []
    data = await _fetch_transactions_from_dton(filters, attributes)
    if not data:
        return transactions

    logger.debug(f"{len(data)} more transactions")
    transactions.extend(data)

    filters["lt__lt"] = int(data[-1].lt)
    while data:
        filters["lt__lt"] = int(data[-1].lt)
        data = await _fetch_transactions_from_dton(filters, attributes)
        logger.debug(f"{len(data)} more transactions")
        transactions.extend(data)

    return transactions


def _parse_jettons_amount(body: str) -> float:
    decoded_in_msg_body = base64.b64decode(body)
    cell = Cell.one_from_boc(decoded_in_msg_body)
    slice_ = cell.begin_parse()
    slice_.skip_bits(96)
    coins = slice_.load_coins()

    return cast(int, coins) / 10**9


def utcdate_from_dton_gen_utime(gen_utime: str) -> datetime:
    return datetime.fromisoformat(f"{gen_utime}+03:00").astimezone(UTC)
