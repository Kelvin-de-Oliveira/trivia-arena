"""
Cobre:
  - _parse_stomp_headers  — parser do frame STOMP CONNECT
  - _build_stomp_connect  — montagem do frame traduzido
  - perform_handshake     — todos os branches de validação 
  - reconexão stateless   — dois handshakes independentes

WebSocket é mockado com AsyncMock; nenhum servidor real é necessário.
"""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.api.websocket.handshake import (
    HandshakeResult,
    _build_stomp_connect,
    _parse_stomp_headers,
    perform_handshake,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_ANON_ID  = "anon:550e8400-e29b-41d4-a716-446655440000"
INVALID_ANON_ID = "anon:nao-e-um-uuid"
FAKE_ROOM_CODE = "ABCD12"


def make_stomp_connect(**headers) -> str:
    """Monta um frame STOMP CONNECT com os headers fornecidos."""
    frame = "CONNECT\n"
    for k, v in headers.items():
        frame += f"{k}:{v}\n"
    frame += "\n\x00"
    return frame


def make_websocket(connect_frame: str) -> AsyncMock:
    """Mock de WebSocket que retorna connect_frame como primeira mensagem."""
    ws = AsyncMock()
    ws.receive_text = AsyncMock(return_value=connect_frame)
    return ws


def make_jwt(user_id: str, name: str = "alice") -> str:
    """Gera um JWT real via core/security para usar nos testes."""
    from app.core.security import create_jwt
    return create_jwt(user_id=user_id, name=name)


# ── _parse_stomp_headers ──────────────────────────────────────────────────────

class TestParseStompHeaders:

    def test_extrai_headers_basicos(self):
        frame = make_stomp_connect(**{
            "player-id": VALID_ANON_ID,
            "room-code": FAKE_ROOM_CODE,
        })
        headers = _parse_stomp_headers(frame)
        assert headers["player-id"] == VALID_ANON_ID
        assert headers["room-code"] == FAKE_ROOM_CODE

    def test_extrai_authorization(self):
        frame = make_stomp_connect(**{
            "player-id": "uuid-1",
            "room-code": FAKE_ROOM_CODE,
            "authorization": "Bearer token123",
        })
        headers = _parse_stomp_headers(frame)
        assert headers["authorization"] == "Bearer token123"

    def test_body_apos_linha_vazia_nao_vaza(self):
        frame = "CONNECT\nplayer-id:uuid-1\n\ncorpo-ignorado\x00"
        headers = _parse_stomp_headers(frame)
        assert "corpo-ignorado" not in headers
        assert headers["player-id"] == "uuid-1"

    def test_null_byte_nao_incluido_nos_headers(self):
        frame = make_stomp_connect(**{"player-id": "uuid-1"})
        headers = _parse_stomp_headers(frame)
        assert "\x00" not in headers


# ── _build_stomp_connect ──────────────────────────────────────────────────────

class TestBuildStompConnect:

    def test_comeca_com_connect(self):
        frame = _build_stomp_connect({"player-id": "uuid-1"})
        assert frame.startswith("CONNECT\n")

    def test_headers_no_formato_chave_valor(self):
        frame = _build_stomp_connect({
            "player-id": "uuid-1",
            "room-code": FAKE_ROOM_CODE,
            "authenticated": "true",
        })
        assert "player-id:uuid-1\n" in frame
        assert "room-code:ABCD12\n" in frame
        assert "authenticated:true\n" in frame

    def test_termina_com_null_byte(self):
        frame = _build_stomp_connect({"player-id": "uuid-1"})
        assert frame.endswith("\n\x00")


# ── perform_handshake ─────────────────────────────────────────────────────────

class TestPerformHandshake:

    @pytest.mark.asyncio
    async def test_anonimo_valido_retorna_result(self):
        ws = make_websocket(make_stomp_connect(**{
            "player-id": VALID_ANON_ID,
            "room-code": FAKE_ROOM_CODE,
        }))
        result = await perform_handshake(ws)
        assert isinstance(result, HandshakeResult)
        assert result.player_id == VALID_ANON_ID
        assert result.room_code == FAKE_ROOM_CODE
        assert result.authenticated is False

    @pytest.mark.asyncio
    async def test_autenticado_coincidente_retorna_result(self):
        user_id = "uuid-autenticado-1"
        token = make_jwt(user_id)
        ws = make_websocket(make_stomp_connect(**{
            "player-id": user_id,
            "room-code": FAKE_ROOM_CODE,
            "authorization": f"Bearer {token}",
        }))
        result = await perform_handshake(ws)
        assert isinstance(result, HandshakeResult)
        assert result.player_id == user_id
        assert result.authenticated is True

    @pytest.mark.asyncio
    async def test_jwt_invalido_envia_erro_e_retorna_none(self):
        ws = make_websocket(make_stomp_connect(**{
            "player-id": "uuid-1",
            "room-code": FAKE_ROOM_CODE,
            "authorization": "Bearer token-invalido",
        }))
        result = await perform_handshake(ws)
        assert result is None
        frame = json.loads(ws.send_text.call_args[0][0])
        assert frame["type"] == "error"
        assert frame["code"] == "UNAUTHENTICATED"
        ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_mismatch_jwt_vs_player_id_envia_player_id_mismatch(self):
        user_id = "uuid-correto"
        token = make_jwt(user_id)
        ws = make_websocket(make_stomp_connect(**{
            "player-id": "uuid-diferente",
            "room-code": FAKE_ROOM_CODE,
            "authorization": f"Bearer {token}",
        }))
        result = await perform_handshake(ws)
        assert result is None
        frame = json.loads(ws.send_text.call_args[0][0])
        assert frame["type"] == "error"
        assert frame["code"] == "PLAYER_ID_MISMATCH"
        ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_anonimo_formato_invalido_envia_invalid_argument(self):
        ws = make_websocket(make_stomp_connect(**{
            "player-id": INVALID_ANON_ID,
            "room-code": FAKE_ROOM_CODE,
        }))
        result = await perform_handshake(ws)
        assert result is None
        frame = json.loads(ws.send_text.call_args[0][0])
        assert frame["type"] == "error"
        assert frame["code"] == "INVALID_ARGUMENT"
        ws.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_frame_upstream_contem_authenticated_false_para_anonimo(self):
        ws = make_websocket(make_stomp_connect(**{
            "player-id": VALID_ANON_ID,
            "room-code": FAKE_ROOM_CODE,
        }))
        result = await perform_handshake(ws)
        assert "authenticated:false" in result.upstream_connect_frame

    @pytest.mark.asyncio
    async def test_frame_upstream_contem_authenticated_true_para_jwt(self):
        user_id = "uuid-jwt-1"
        token = make_jwt(user_id)
        ws = make_websocket(make_stomp_connect(**{
            "player-id": user_id,
            "room-code": FAKE_ROOM_CODE,
            "authorization": f"Bearer {token}",
        }))
        result = await perform_handshake(ws)
        assert "authenticated:true" in result.upstream_connect_frame

    @pytest.mark.asyncio
    async def test_frame_upstream_nao_contem_authorization(self):
        """Gateway nunca repassa o JWT ao Game Service (§6.2)."""
        user_id = "uuid-jwt-2"
        token = make_jwt(user_id)
        ws = make_websocket(make_stomp_connect(**{
            "player-id": user_id,
            "room-code": FAKE_ROOM_CODE,
            "authorization": f"Bearer {token}",
        }))
        result = await perform_handshake(ws)
        assert "authorization" not in result.upstream_connect_frame


# ── Reconexão stateless (§6.4) ────────────────────────────────────────────────

class TestReconexaoStateless:

    @pytest.mark.asyncio
    async def test_dois_handshakes_independentes_sem_estado_compartilhado(self):
        """
        cada reconexão é um novo handshake completo.
        o resultado do segundo não deve depender do primeiro.
        """
        id_1 = VALID_ANON_ID
        id_2 = "anon:12345678-1234-1234-1234-123456789abc"

        ws1 = make_websocket(make_stomp_connect(**{
            "player-id": id_1,
            "room-code": FAKE_ROOM_CODE,
        }))
        ws2 = make_websocket(make_stomp_connect(**{
            "player-id": id_2,
            "room-code": FAKE_ROOM_CODE,
        }))

        result1 = await perform_handshake(ws1)
        result2 = await perform_handshake(ws2)

        assert result1.player_id == id_1
        assert result2.player_id == id_2
        assert result1.player_id != result2.player_id