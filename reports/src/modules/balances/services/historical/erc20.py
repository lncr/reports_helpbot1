from datetime import datetime

from httpx import QueryParams
from loguru import logger

from src.config import settings
from src.core.dto import Wallet
from src.core.http import send_request
from src.modules.transfers.dto import ETHTransfersList
from src.modules.transfers.services.eth import get_block_by_timestamp


async def get_historical_eth_balance(
    wallet: Wallet,
    current_balance: float,
    target_date: datetime,
) -> float:
    target_block = await get_block_by_timestamp(target_date, "before")
    transactions = await transactions_from_now_to_target(wallet, target_block)
    if not transactions.root:
        logger.debug("no transactions found")
        return current_balance

    return current_balance - _calculate_balance_change_from_transactions(wallet, transactions)


async def transactions_from_now_to_target(wallet: Wallet, target_block: int) -> ETHTransfersList:
    params = QueryParams(
        module="account",
        action="txlist",
        address=wallet.address,
        startblock=target_block,
        endblock=99999999,
        sort="asc",
        apikey=settings.ETHERSCAN_API_KEY,
    )

    response = await send_request("GET", settings.ETHERSCAN_API_BASE_URL, params=params)
    return ETHTransfersList.model_validate(response.json()["result"])


def _calculate_balance_change_from_transactions(wallet: Wallet, transactions: ETHTransfersList) -> float:
    net_balance_change = 0.0
    for tx in transactions.root:
        # Convert value from Wei to Ether (1 Ether = 10^18 Wei)
        logger.debug(tx)
        logger.debug(f"Value: {tx.value}")
        value_in_ether = int(tx.value) / 10**18

        # Outgoing transaction
        if tx.from_address.lower() == wallet.address.lower():
            net_balance_change -= value_in_ether

            # Calculate gas cost in Wei and convert to Ether
            gas_cost_in_wei = int(tx.gas_used) * int(tx.gas_price)
            gas_cost_in_ether = gas_cost_in_wei / 10**18
            net_balance_change -= gas_cost_in_ether

        # Incoming transaction
        elif tx.to.lower() == wallet.address.lower():
            net_balance_change += value_in_ether

    return net_balance_change
