"""
Fábrica de canais gRPC para Game Service e User Service.

"""

import logging

import grpc.aio

from app.core.config import settings

logger = logging.getLogger(__name__)

_game_channel: grpc.aio.Channel | None = None
_user_channel: grpc.aio.Channel | None = None


async def open_channels() -> None:
    global _game_channel, _user_channel

    _game_channel = grpc.aio.insecure_channel(settings.game_grpc_address)
    _user_channel = grpc.aio.insecure_channel(settings.user_grpc_address)

    logger.info(
        "Canais gRPC abertos | game=%s | user=%s",
        settings.game_grpc_address,
        settings.user_grpc_address,
    )


async def close_channels() -> None:
    global _game_channel, _user_channel

    if _game_channel:
        await _game_channel.close()
        _game_channel = None

    if _user_channel:
        await _user_channel.close()
        _user_channel = None

    logger.info("Canais gRPC fechados.")


def get_game_channel() -> grpc.aio.Channel:
    if _game_channel is None:
        raise RuntimeError("canal gRPC do Game Service não inicializado")
    return _game_channel


def get_user_channel() -> grpc.aio.Channel:
    if _user_channel is None:
        raise RuntimeError("canal gRPC do User Service não inicializado")
    return _user_channel