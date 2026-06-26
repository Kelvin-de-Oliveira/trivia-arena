"""
Validação de app/clients/channel_factory.py.
Testa gerenciamento de estado dos canais gRPC sem abrir conexões reais.
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.clients import channel_factory
from app.clients.channel_factory import (
    close_channels,
    get_game_channel,
    get_user_channel,
    open_channels,
)


@pytest.fixture(autouse=True)
async def reset_channels():
    """Garante estado limpo (canais = None) antes e depois de cada teste."""
    channel_factory._game_channel = None
    channel_factory._user_channel = None
    yield
    channel_factory._game_channel = None
    channel_factory._user_channel = None


def make_mock_channel() -> AsyncMock:
    mock = AsyncMock()
    mock.close = AsyncMock()
    return mock


class TestChannelFactory:

    # ── Antes de open_channels ────────────────────────────────────────────

    def test_get_game_channel_before_open_raises(self):
        with pytest.raises(RuntimeError, match="não inicializado"):
            get_game_channel()

    def test_get_user_channel_before_open_raises(self):
        with pytest.raises(RuntimeError, match="não inicializado"):
            get_user_channel()

    # ── Após open_channels ────────────────────────────────────────────────

    async def test_get_game_channel_after_open_returns_channel(self):
        with patch("grpc.aio.insecure_channel", return_value=make_mock_channel()):
            await open_channels()
            assert get_game_channel() is not None

    async def test_get_user_channel_after_open_returns_channel(self):
        with patch("grpc.aio.insecure_channel", return_value=make_mock_channel()):
            await open_channels()
            assert get_user_channel() is not None

    async def test_open_channels_creates_distinct_channels(self):
        mock_a = make_mock_channel()
        mock_b = make_mock_channel()
        with patch("grpc.aio.insecure_channel", side_effect=[mock_a, mock_b]):
            await open_channels()
            assert get_game_channel() is not get_user_channel()

    # ── Após close_channels ───────────────────────────────────────────────

    async def test_get_game_channel_after_close_raises(self):
        with patch("grpc.aio.insecure_channel", return_value=make_mock_channel()):
            await open_channels()
        await close_channels()
        with pytest.raises(RuntimeError, match="não inicializado"):
            get_game_channel()

    async def test_get_user_channel_after_close_raises(self):
        with patch("grpc.aio.insecure_channel", return_value=make_mock_channel()):
            await open_channels()
        await close_channels()
        with pytest.raises(RuntimeError, match="não inicializado"):
            get_user_channel()

    async def test_close_channels_is_idempotent(self):
        """Chamar close sem open não deve levantar exceção."""
        await close_channels()  