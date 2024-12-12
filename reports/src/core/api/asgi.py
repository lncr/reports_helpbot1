from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sentry_sdk import init as sentry_init
from sentry_sdk.integrations.loguru import LoguruIntegration

from src.config import settings
from src.core.types.singleton import SingletonMeta
from src.core.utils import create_media_if_not_exists
from src.modules.metrics.routers import router as metrics_router

from .routers.services import router as services_router
from .routers.v1 import router as api_v1_router


async def _lifespan_on_startup(app: FastAPI) -> None:
    _ = app
    create_media_if_not_exists()


async def _lifespan_on_shutdown(app: FastAPI) -> None:
    _ = app


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await _lifespan_on_startup(app)
    yield
    await _lifespan_on_shutdown(app)


class AsgiConfig(metaclass=SingletonMeta):
    __slots__ = ("_app",)
    _app: FastAPI

    def __init__(self) -> None:
        if settings.SENTRY_DSN:
            sentry_init(
                dsn=settings.SENTRY_DSN,
                enable_tracing=True,
                traces_sample_rate=1.0,
                profiles_sample_rate=1.0,
                integrations=[LoguruIntegration()],
            )

        self._app = FastAPI(
            title="Bemo Reports API",
            version="1.0",
            root_path="/api",
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
            lifespan=lifespan,
        )

        self._app.include_router(api_v1_router)
        self._app.include_router(services_router)
        self._app.include_router(metrics_router)

    def get_app(self) -> FastAPI:
        """Get ASGI get_app."""

        return self._app
