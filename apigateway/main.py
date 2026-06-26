import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.clients.channel_factory import close_channels, open_channels
from app.middleware.error_handler import register_exception_handlers
from app.core.config import settings
from app.core.logging import setup_logging


setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "API Gateway iniciando | porta=%s | game_grpc=%s | user_grpc=%s",
        settings.port,
        settings.game_grpc_address,
        settings.user_grpc_address,
    )
    await open_channels()
    yield
    await close_channels()
    logger.info("API Gateway encerrando.")

app = FastAPI(
    title="API Gateway — Trivia Arena",
    version="0.1.0",
    docs_url="/docs",
    lifespan=lifespan,
)

register_exception_handlers(app)

@app.get("/health", tags=["infra"])
async def health_check() -> dict:
    return {"status": "ok"}