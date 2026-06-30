import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.clients.channel_factory import close_channels, open_channels
from app.middleware.error_handler import register_exception_handlers
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.rest import auth
from app.api.rest import rooms
from app.api.rest import users
from app.api.websocket import ws_proxy


setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "API Gateway iniciando | porta=%s | game_grpc=%s | game_ws=%s | user_grpc=%s",
        settings.port,
        settings.game_grpc_address,
        settings.game_ws_url,
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


register_exception_handlers(app)

app.include_router(auth.router)
app.include_router(rooms.router)
app.include_router(users.router)
app.include_router(ws_proxy.router)


@app.get("/health", tags=["infra"])
async def health_check() -> dict:
    return {"status": "ok"}
