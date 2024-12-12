from datetime import datetime

from src.core.const import DTON_URL
from src.core.dto import Wallet
from src.core.http import send_request
from src.modules.transfers.dto import DTONQuery, TONTransfersList


async def get_historical_ton_balance(wallet: Wallet, target_date: datetime, current_balance: float) -> float:
    transactions = await get_transactions(wallet, target_date)
    change = calculate_balance_change_by_transactions(wallet, transactions)
    return current_balance - change


async def get_transactions(wallet: Wallet, target_date: datetime) -> TONTransfersList:
    # NOTE: if you replace DTON, pls check out the `function` where is the work with timezones
    # DTON sends time in Moscow timezone, so you probably gonna need to change it
    query = DTONQuery.model_validate(
        {
            "query": f"""{{
            raw_transactions(
                address_friendly: "{wallet.address}"
                gen_utime__gte: "{target_date.strftime("%Y-%m-%dT%H:%M:%S")}"
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
    )

    # Define the URL of the dTON GraphQL API endpoint
    response = await send_request("POST", DTON_URL, data=query)
    data = response.json()

    # Check if the response is successful
    if "errors" in data and (errors := data["errors"]):
        raise Exception(f"Error fetching data: {errors}")

    return TONTransfersList.model_validate(response.json()["data"]["raw_transactions"])


def calculate_balance_change_by_transactions(wallet: Wallet, transactions: TONTransfersList) -> float:
    net_balance_change = 0.0

    for tx in transactions.root:
        # Process incoming messages
        if (
            tx.in_msg_src_addr_address_hex
            and tx.in_msg_value_grams
            and tx.in_msg_src_addr_address_hex != wallet.address
        ):
            value_in_ton = float(tx.in_msg_value_grams) / 10**9
            net_balance_change += value_in_ton

        # Process outgoing messages
        if tx.out_msg_dest_addr_address_hex:
            assert tx.out_msg_value_grams
            for out_value in tx.out_msg_value_grams:
                if tx.out_msg_dest_addr_address_hex[0] != wallet.address:
                    value_in_ton = int(out_value) / 10**9
                    net_balance_change -= value_in_ton

        # Add gas cost
        compute_ph_gas_fees = int(tx.compute_ph_gas_fees) if tx.compute_ph_gas_fees else 0
        action_ph_total_fwd_fees = int(tx.action_ph_total_fwd_fees) if tx.action_ph_total_fwd_fees else 0
        action_ph_total_action_fees = int(tx.action_ph_total_action_fees) if tx.action_ph_total_action_fees else 0
        storage_ph_storage_fees_collected = (
            int(tx.storage_ph_storage_fees_collected) if tx.storage_ph_storage_fees_collected else 0
        )
        storage_ph_storage_fees_due = int(tx.storage_ph_storage_fees_due) if tx.storage_ph_storage_fees_due else 0
        in_msg_fwd_fee_grams = int(tx.in_msg_fwd_fee_grams) if tx.in_msg_fwd_fee_grams else 0
        in_msg_ihr_fee_grams = int(tx.in_msg_ihr_fee_grams) if tx.in_msg_ihr_fee_grams else 0

        gas_cost_in_nanotons = (
            compute_ph_gas_fees
            + action_ph_total_fwd_fees
            + action_ph_total_action_fees
            + storage_ph_storage_fees_collected
            + storage_ph_storage_fees_due
            + in_msg_fwd_fee_grams
            + in_msg_ihr_fee_grams
        )
        gas_cost_in_ton = gas_cost_in_nanotons / 10**9
        net_balance_change -= gas_cost_in_ton

    return net_balance_change
