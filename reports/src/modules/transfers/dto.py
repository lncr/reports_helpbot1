from datetime import datetime

from pydantic import Field, RootModel

from src.core.const import Network, Side
from src.core.dto import BaseDTO


class Transfer(BaseDTO):
    time: datetime
    side: Side
    value: float
    symbol: str
    note: str
    account_name: str
    address: str
    network: Network


class TransfersReport(RootModel[list[Transfer]]): ...


class TONTransfer(BaseDTO):
    gen_utime: str
    account_storage_balance_grams: str | int | float
    in_msg_value_grams: str | int | float | None
    out_msg_value_grams: list[str | int | float] | None
    out_msg_dest_addr_address_hex: list[str] | None
    in_msg_src_addr_address_hex: str | None
    in_msg_comment: str | None
    in_msg_fwd_fee_grams: str | int | float | None
    compute_ph_gas_fees: str | int | float | None
    action_ph_total_fwd_fees: str | int | float | None
    action_ph_total_action_fees: str | int | float | None
    storage_ph_storage_fees_collected: str | int | float | None
    storage_ph_storage_fees_due: str | int | float | None
    in_msg_ihr_fee_grams: str | int | float | None


class TONTransfersList(RootModel[list[TONTransfer]]): ...


class JettonTransfer(BaseDTO):
    query_id: str
    source: str | None
    destination: str | None
    amount: float
    source_wallet: str
    jetton_master: str
    transaction_hash: str
    transaction_lt: str
    transaction_now: int
    response_destination: str | None
    custom_payload: str | None
    forward_ton_amount: str | None
    forward_payload: str | None


class JettonTransfersList(RootModel[list[JettonTransfer]]): ...


class ETHTransfer(BaseDTO):
    block_number: str = Field(alias="blockNumber", serialization_alias="blockNumber")
    time_stamp: str = Field(alias="timeStamp", serialization_alias="timeStamp")
    hash: str
    nonce: str
    block_hash: str = Field(alias="blockHash", serialization_alias="blockHash")
    from_address: str = Field(alias="from", serialization_alias="from")
    contract_address: str = Field(alias="contractAddress", serialization_alias="contractAddress")
    to: str
    value: str
    token_name: str | None = Field(None, alias="tokenName", serialization_alias="tokenName")
    token_symbol: str | None = Field(None, alias="tokenSymbol", serialization_alias="tokenSymbol")
    token_decimal: str | None = Field(None, alias="tokenDecimal", serialization_alias="tokenDecimal")
    transaction_index: str = Field(alias="transactionIndex", serialization_alias="transactionIndex")
    gas: str
    gas_price: str = Field(alias="gasPrice", serialization_alias="gasPrice")
    gas_used: str = Field(alias="gasUsed", serialization_alias="gasUsed")
    cumulative_gas_used: str = Field(alias="cumulativeGasUsed", serialization_alias="cumulativeGasUsed")
    input: str
    confirmations: str


class ETHTransfersList(RootModel[list[ETHTransfer]]): ...


class DTONQuery(BaseDTO):
    query: str


class DtonTransaction(BaseDTO):
    """
    Check out the possible fields here:
    search for `TransactionGQ` model at `https://dton.io/graphql/` documentation
    """

    in_msg_body: str
    in_msg_op_code: str | int | float
    in_msg_dest_addr_address_hex: str
    in_msg_src_addr_address_hex: str
    gen_utime: str
    lt: str | int | float
