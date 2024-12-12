import sys
from pathlib import Path
from uuid import uuid4

from loguru import logger
from pydantic import UUID4
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ("settings",)


class Settings(BaseSettings):

    ROOT_DIR: Path = Path(__file__).parent.parent.resolve()
    DEBUG: bool = False

    SENTRY_DSN: str = ""

    ETHERSCAN_API_BASE_URL: str = "https://api.etherscan.io/api"
    ETHERSCAN_API_KEY: str = ""
    CMC_API_KEY: UUID4 = uuid4()
    OPEN_EXCHANGE_RATE_API_ID: str = ""

    TON_CONFIG: Path = ROOT_DIR / "config.json"
    STTON_ADDRESS: str = "EQDNhy-nxYFgUqzfUzImBEP67JqsyMIcyk2S5_RwNNEYku0k"

    INPUT_DATA_DIR: Path = ROOT_DIR / "static"
    TOKEN_LIST_ETH_CSV: Path = INPUT_DATA_DIR / "token_list_eth.csv"
    ADDRESS_BOOK_ETH_CSV: Path = INPUT_DATA_DIR / "address_book_eth.csv"
    ADDRESS_BOOK_TON_CSV: Path = INPUT_DATA_DIR / "address_book_ton.csv"
    ADDRESS_BOOK_JETTONS_CSV: Path = INPUT_DATA_DIR / "address_book_jettons.csv"

    MEDIA_DIR: Path = ROOT_DIR / "media"
    OPEN_EXCHANGE_RATE_DATA: Path = MEDIA_DIR / "open_exchange_rates.csv"

    DTON_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=f"{ROOT_DIR}/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_assignment=True,
        extra="ignore",
    )


settings = Settings()

# Logging Configuration
logger.remove(0)
logger.add(
    sys.stderr,
    format="<red>[{level}]</red> Message : <green>{message}</green> @ {time:YYYY-MM-DD HH:mm:ss}",
    colorize=True,
    level=("DEBUG" if settings.DEBUG else "INFO"),
    backtrace=True,
    diagnose=True,
)
