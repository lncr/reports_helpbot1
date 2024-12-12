from enum import StrEnum

from src.config import settings

DTON_URL: str = f"https://dton.co/{settings.DTON_API_KEY}/graphql"


class JettonActionType(StrEnum):
    JettonSwap = "JettonSwap"
    JettonTransfer = "JettonTransfer"
    Deposit = "Deposit"
    Withdraw = "Withdraw"
    Burn = "Burn"
    Mint = "Mint"


class Side(StrEnum):
    IN = "in"
    OUT = "out"


class Network(StrEnum):
    ETH = "ETH"
    TON = "TON"
