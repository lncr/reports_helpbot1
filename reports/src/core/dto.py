from datetime import datetime

from pydantic import BaseModel, ConfigDict, RootModel

from src.core.const import JettonActionType, Side


class BaseDTO(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        from_attributes=True,
    )


class Wallet(BaseDTO):
    address: str
    account_name: str


class Wallets(RootModel[list[Wallet]]): ...


class Token(BaseDTO):
    address: str
    symbol: str


class JettonAddressBook(RootModel[list[Token]]):
    def get(self, address: str, _default: Token | None = None) -> Token | None:
        """get token by address in jetton address book"""
        for token in self.root:
            if token.address.lower() == address.lower():
                return token
        return _default


class JettonWallet(Wallet):
    jetton_master: str
    symbol: str


class JettonTransaction(BaseDTO):
    type: JettonActionType
    date: datetime
    address: str
    note: str = ""
    side: Side
    amount: float
    account_name: str
    jetton_master: str | None
    symbol: str

    model_config = ConfigDict(
        frozen=False,
        from_attributes=True,
    )


class JettonTransactionList(RootModel[list[JettonTransaction]]): ...
