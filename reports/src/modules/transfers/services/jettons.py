from datetime import UTC, datetime
from typing import Any, TypedDict

from httpx import QueryParams, Response
from loguru import logger
from pytoniq import Address

from src.core.const import JettonActionType, Side
from src.core.dto import JettonTransaction, JettonWallet
from src.core.http import send_request
from src.modules.transfers.services.bemo_staking import fetch_bemo_staking_transactions
from src.modules.transfers.services.const import EVAA_ADDRESS

__all__ = ("fetch_jetton_transfers",)


async def fetch_jetton_transfers(
    wallet: JettonWallet,
    start_date: datetime,
    end_date: datetime,
) -> list[JettonTransaction]:
    """Fetches jetton transfers for a given wallet."""
    transactions = await _fetch_transactions_from_tonapi(wallet, start_date, end_date)
    for transaction in transactions:
        if transaction.jetton_master and (wallet.jetton_master.lower() == transaction.jetton_master.lower()):
            transaction.symbol = wallet.symbol

    bemo_staking_transactions = await fetch_bemo_staking_transactions(wallet, start_date, end_date)
    transactions.extend(bemo_staking_transactions)

    return transactions


async def _fetch_transactions_from_tonapi(
    wallet: JettonWallet, start_date: datetime, end_date: datetime
) -> list[JettonTransaction]:
    url = f"https://tonapi.io/v2/accounts/{wallet.address}/events"
    start_ts = int(start_date.timestamp())
    end_ts = int(end_date.timestamp())
    limit = 100
    params = QueryParams(limit=limit, start_date=start_ts, end_date=end_ts)
    result = []

    while True:
        response = await send_request("GET", url, params=params)
        transactions, next_lt = _parse_tonapi_response(wallet, response)
        result.extend(transactions)
        if not next_lt:
            break

        params = QueryParams(limit=limit, before_lt=next_lt, start_date=start_ts, end_date=end_ts)

    return result


def _parse_tonapi_response(wallet: JettonWallet, response: Response) -> tuple[list[JettonTransaction], int]:
    data = response.json()
    next_lt = int(data.get("next_from", 0))
    transactions = _parse_tonapi_events(data, wallet)
    return transactions, next_lt


def _parse_tonapi_events(data: dict[str, Any], wallet: JettonWallet) -> list[JettonTransaction]:
    transactions: list[JettonTransaction] = []
    for event in data.get("events", []):
        logger.debug(f"Event ID: {event['event_id']}")
        if event.get("in_progress", False):
            continue
        transactions.extend(_parse_tonapi_actions(event, wallet))
    return transactions


def _parse_tonapi_actions(event: dict[str, Any], wallet: JettonWallet) -> list[JettonTransaction]:
    transactions: list[JettonTransaction] = []
    for action in event.get("actions", []):
        if action.get("status") != "ok":
            continue

        action_type = action.get("type")
        if action_type == JettonActionType.JettonSwap:
            transaction, transaction_2 = _handle_jetton_swap_action(event["timestamp"], wallet, action)
            transactions.append(transaction_2)
        elif action_type == JettonActionType.JettonTransfer:
            transaction = _handle_jetton_transfer(event["timestamp"], wallet, action)
        else:
            logger.warning(f"No handler for action {action_type}")
            continue
        transactions.append(transaction)
    return transactions


def _handle_jetton_transfer(timestamp: int, wallet: JettonWallet, action: dict[str, Any]) -> JettonTransaction:
    transaction = action[JettonActionType.JettonTransfer]

    if wallet.address == (sender_wallet := transaction["senders_wallet"]):
        side = Side.OUT
        address = transaction["recipients_wallet"]
    else:
        side = Side.IN
        address = sender_wallet

    amount = float(transaction["amount"]) / 10 ** transaction["jetton"]["decimals"]
    note = transaction.get("comment", "")

    sender_address = Address(sender_wallet)
    recipient_address = Address(address)
    evaa_address = Address(EVAA_ADDRESS)

    if sender_address == evaa_address:
        note = "EVAA withdrawal"
    elif recipient_address == evaa_address:
        note = "EVAA deposit"

    return JettonTransaction(
        date=datetime.fromtimestamp(timestamp, UTC),
        symbol=wallet.symbol,
        account_name=wallet.account_name,
        type=JettonActionType.JettonTransfer,
        side=side,
        amount=amount,
        address=address,
        jetton_master=transaction["jetton"]["address"],
        note=note,
    )


def _handle_jetton_swap_action(
    timestamp: int,
    wallet: JettonWallet,
    action: dict[str, Any],
) -> tuple[JettonTransaction, JettonTransaction]:
    action_type = JettonActionType.JettonSwap
    transaction = action[action_type]

    if any(("ton_out" in transaction, "ton_in" in transaction)):
        first, second = _parse_jetton_to_ton_swap(transaction)
    else:
        first, second = _parse_jetton_to_jetton_swap(wallet, transaction)

    return (
        JettonTransaction(
            type=action_type,
            note=action["simple_preview"]["description"],
            date=datetime.fromtimestamp(timestamp, UTC),
            address=wallet.jetton_master,
            side=first["side"],
            amount=first["amount"],
            symbol=first["symbol"],
            jetton_master=first["jetton_master"],
            account_name=wallet.account_name,
        ),
        JettonTransaction(
            type=action_type,
            note=action["simple_preview"]["description"],
            date=datetime.fromtimestamp(timestamp, UTC),
            address=wallet.jetton_master,
            side=second["side"],
            amount=second["amount"],
            symbol=second["symbol"],
            jetton_master=second["jetton_master"],
            account_name=wallet.account_name,
        ),
    )


class _JettonSwap(TypedDict):
    side: Side
    amount: float
    symbol: str
    jetton_master: str | None


def _parse_jetton_to_ton_swap(transaction: dict[str, Any]) -> tuple[_JettonSwap, _JettonSwap]:
    if ton_out := transaction.get("ton_out"):
        jm_in = transaction["jetton_master_in"]
        amount = float(transaction["amount_in"]) / 10 ** jm_in["decimals"]
        return (
            {"side": Side.OUT, "amount": amount, "symbol": jm_in["symbol"], "jetton_master": jm_in["address"]},
            {"side": Side.IN, "amount": float(ton_out) / 1e9, "symbol": "TON", "jetton_master": None},
        )

    jm_out = transaction["jetton_master_out"]
    amount = float(transaction["amount_out"]) / 10 ** jm_out["decimals"]
    return (
        {"side": Side.IN, "amount": amount, "symbol": jm_out["symbol"], "jetton_master": jm_out["address"]},
        {"side": Side.OUT, "amount": float(transaction["ton_in"]) / 1e9, "symbol": "TON", "jetton_master": None},
    )


def _parse_jetton_to_jetton_swap(wallet: JettonWallet, transaction: dict[str, Any]) -> tuple[_JettonSwap, _JettonSwap]:
    jm_in = transaction["jetton_master_in"]
    jm_out = transaction["jetton_master_out"]
    if jm_in["address"].lower() == wallet.jetton_master.lower():
        amount = float(transaction["amount_in"]) / 10 ** jm_in["decimals"]
        amount_out = float(transaction["amount_out"]) / 10 ** jm_out["decimals"]
        return {"side": Side.IN, "amount": amount, "symbol": jm_in["symbol"], "jetton_master": jm_in["address"]}, {
            "side": Side.OUT,
            "amount": amount_out,
            "symbol": jm_out["symbol"],
            "jetton_master": jm_out["address"],
        }

    amount = float(transaction["amount_out"]) / 10 ** jm_out["decimals"]
    amount_in = float(transaction["amount_in"]) / 10 ** jm_in["decimals"]
    return {"side": Side.OUT, "amount": amount, "symbol": jm_out["symbol"], "jetton_master": jm_out["address"]}, {
        "side": Side.IN,
        "amount": amount_in,
        "symbol": jm_in["symbol"],
        "jetton_master": jm_in["address"],
    }
