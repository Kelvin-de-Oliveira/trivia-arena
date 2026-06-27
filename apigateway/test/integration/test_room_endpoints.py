"""
Fluxo testado: HTTP → router → room_service → ensure_identity → (GameServiceClient mockado).

Usa dependency_overrides para:
  - injetar um GameServiceClient mockado (sem gRPC real), igual ao test_auth_endpoints.py
  - simular usuário autenticado/anônimo sobrescrevendo get_optional_user_id
    diretamente (sem precisar gerar um JWT real)

ensure_identity() NÃO é mockado: é exercitado de verdade em cada request,
então os testes de 403 (mismatch) e 400 (formato anon inválido) cobrem o
comportamento real do identity_guard, não um duplo.

Referência: https://fastapi.tiangolo.com/advanced/testing-dependencies/
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rest import rooms
from app.clients.game_service_client import GameServiceClient
from app.dependencies.auth_deps import get_optional_user_id
from app.dependencies.grpc_deps import get_game_client
from app.exceptions import (
    FailedPreconditionError,
    NotFoundError,
    PermissionDeniedError,
    UpstreamUnavailableError,
)
from app.middleware.error_handler import register_exception_handlers
from app.schemas.room_schemas import (
    GetRoomResponse,
    JoinRoomResponse,
    PlayerSchema,
    RoomStatus,
    Theme,
)

FAKE_USER_ID = "uuid-fake-1"
OTHER_USER_ID = "uuid-fake-outro"
FAKE_ROOM_CODE = "ABCD12"
VALID_ANON_ID = "anon:550e8400-e29b-41d4-a716-446655440000"
INVALID_ANON_ID = "anon:nao-e-um-uuid"

_NO_OVERRIDE = object()  # sentinela: não sobrescrever get_optional_user_id


def build_test_app(mock_client: GameServiceClient, jwt_user_id=_NO_OVERRIDE) -> FastAPI:
    """
    App mínimo com apenas o router de rooms.

    jwt_user_id:
        _NO_OVERRIDE -> não sobrescreve get_optional_user_id (sem token = anônimo)
        None         -> força anônimo, equivalente a request sem Authorization
        "algum-id"   -> força usuário autenticado com esse user_id (sub do JWT)
    """
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(rooms.router)
    app.dependency_overrides[get_game_client] = lambda: mock_client
    if jwt_user_id is not _NO_OVERRIDE:
        app.dependency_overrides[get_optional_user_id] = lambda: jwt_user_id
    return app


def make_mock_client(**method_results) -> GameServiceClient:
    """
    method_results: nome_do_metodo=valor_de_retorno, ou uma instância de
    Exception para simular o client levantando erro (side_effect).
    """
    client = AsyncMock(spec=GameServiceClient)
    for method_name, result in method_results.items():
        mock_method = getattr(client, method_name)
        if isinstance(result, Exception):
            mock_method.side_effect = result
        else:
            mock_method.return_value = result
    return client


def make_player(player_id=FAKE_USER_ID, name="alice", anon=False, score=0):
    return PlayerSchema(player_id=player_id, player_name=name, is_anonymous=anon, score=score)


# ── POST /rooms ──────────────────────────────────────────────────────────────

class TestCreateRoomEndpoint:

    def _body(self, **overrides):
        body = {
            "creator_id": FAKE_USER_ID,
            "creator_name": "alice",
            "is_anonymous": False,
            "max_players": 4,
            "num_questions": 10,
            "theme": Theme.science.value,
        }
        body.update(overrides)
        return body

    def test_authenticated_matching_id_returns_201(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body())
        assert r.status_code == 201
        assert r.json()["room_code"] == FAKE_ROOM_CODE

    def test_passes_correct_args_to_client(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        client.post("/rooms", json=self._body())
        mock.create_room.assert_awaited_once_with(
            creator_id=FAKE_USER_ID,
            creator_name="alice",
            is_anonymous=False,
            max_players=4,
            num_questions=10,
            theme=Theme.science,
        )

    def test_authenticated_mismatched_creator_id_returns_403(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body(creator_id=OTHER_USER_ID))
        assert r.status_code == 403
        assert r.json()["error"] == "PERMISSION_DENIED"
        mock.create_room.assert_not_awaited()

    def test_anonymous_valid_id_returns_201(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=None), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body(creator_id=VALID_ANON_ID, is_anonymous=True))
        assert r.status_code == 201

    def test_anonymous_invalid_id_format_returns_400(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=None), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body(creator_id=INVALID_ANON_ID, is_anonymous=True))
        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_ARGUMENT"
        mock.create_room.assert_not_awaited()

    def test_missing_required_field_returns_400(self):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        body = self._body()
        del body["theme"]
        r = client.post("/rooms", json=body)
        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_ARGUMENT"

    @pytest.mark.parametrize("max_players", [1, 11])
    def test_max_players_out_of_range_returns_400(self, max_players):
        mock = make_mock_client(create_room=FAKE_ROOM_CODE)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body(max_players=max_players))
        assert r.status_code == 400

    def test_upstream_unavailable_returns_503(self):
        mock = make_mock_client(create_room=UpstreamUnavailableError("game service indisponível"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post("/rooms", json=self._body())
        assert r.status_code == 503


# ── POST /rooms/{code}/join ───────────────────────────────────────────────────

class TestJoinRoomEndpoint:

    def _body(self, **overrides):
        body = {"player_id": FAKE_USER_ID, "player_name": "bob", "is_anonymous": False}
        body.update(overrides)
        return body

    def _fake_response(self):
        return JoinRoomResponse(
            players=[make_player(name="bob")],
            status=RoomStatus.WAITING,
            theme=Theme.science,
            max_players=4,
            creator_id=OTHER_USER_ID,
            num_questions=10,
        )

    def test_authenticated_matching_id_returns_200(self):
        mock = make_mock_client(join_room=self._fake_response())
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/join", json=self._body())
        assert r.status_code == 200
        assert r.json()["status"] == "WAITING"

    def test_passes_room_code_from_path_to_client(self):
        mock = make_mock_client(join_room=self._fake_response())
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        client.post(f"/rooms/{FAKE_ROOM_CODE}/join", json=self._body())
        mock.join_room.assert_awaited_once_with(
            room_code=FAKE_ROOM_CODE,
            player_id=FAKE_USER_ID,
            player_name="bob",
            is_anonymous=False,
        )

    def test_authenticated_mismatched_player_id_returns_403(self):
        mock = make_mock_client(join_room=self._fake_response())
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/join", json=self._body(player_id=OTHER_USER_ID))
        assert r.status_code == 403
        # ensure_identity levanta PermissionDeniedError genérico (não PlayerIdMismatchError).
        # Se isso mudar no identity_guard, este teste deve falhar e avisar a mudança de contrato.
        assert r.json()["error"] == "PERMISSION_DENIED"
        mock.join_room.assert_not_awaited()

    def test_anonymous_invalid_id_format_returns_400(self):
        mock = make_mock_client(join_room=self._fake_response())
        client = TestClient(build_test_app(mock, jwt_user_id=None), raise_server_exceptions=False)
        r = client.post(
            f"/rooms/{FAKE_ROOM_CODE}/join",
            json=self._body(player_id=INVALID_ANON_ID, is_anonymous=True),
        )
        assert r.status_code == 400

    def test_room_not_found_returns_404(self):
        mock = make_mock_client(join_room=NotFoundError("sala não encontrada"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/join", json=self._body())
        assert r.status_code == 404
        assert r.json()["error"] == "NOT_FOUND"

    def test_room_full_returns_409(self):
        mock = make_mock_client(join_room=FailedPreconditionError("sala cheia"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/join", json=self._body())
        assert r.status_code == 409


# ── GET /rooms/{code} ─────────────────────────────────────────────────────────

class TestGetRoomEndpoint:

    def _fake_response(self):
        return GetRoomResponse(
            room_code=FAKE_ROOM_CODE,
            status=RoomStatus.WAITING,
            theme=Theme.science,
            max_players=4,
            num_questions=10,
            players=[make_player()],
            creator_id=FAKE_USER_ID,
        )

    def test_no_auth_required_returns_200(self):
        mock = make_mock_client(get_room=self._fake_response())
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.get(f"/rooms/{FAKE_ROOM_CODE}")
        assert r.status_code == 200
        assert r.json()["room_code"] == FAKE_ROOM_CODE

    def test_passes_room_code_from_path(self):
        mock = make_mock_client(get_room=self._fake_response())
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        client.get(f"/rooms/{FAKE_ROOM_CODE}")
        mock.get_room.assert_awaited_once_with(room_code=FAKE_ROOM_CODE)

    def test_room_not_found_returns_404(self):
        mock = make_mock_client(get_room=NotFoundError("sala não encontrada"))
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.get(f"/rooms/{FAKE_ROOM_CODE}")
        assert r.status_code == 404


# ── POST /rooms/{code}/start ──────────────────────────────────────────────────

class TestStartGameEndpoint:

    def test_creator_can_start_returns_200(self):
        mock = make_mock_client(start_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/start", json={"requester_id": FAKE_USER_ID})
        assert r.status_code == 200
        assert r.json()["started"] is True

    def test_identity_mismatch_returns_403_without_calling_client(self):
        mock = make_mock_client(start_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/start", json={"requester_id": OTHER_USER_ID})
        assert r.status_code == 403
        assert r.json()["error"] == "PERMISSION_DENIED"
        mock.start_game.assert_not_awaited()

    def test_non_creator_rejected_by_game_service_returns_403(self):
        mock = make_mock_client(start_game=PermissionDeniedError("apenas o criador pode iniciar"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/start", json={"requester_id": FAKE_USER_ID})
        assert r.status_code == 403

    def test_room_not_found_returns_404(self):
        mock = make_mock_client(start_game=NotFoundError("sala não encontrada"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(f"/rooms/{FAKE_ROOM_CODE}/start", json={"requester_id": FAKE_USER_ID})
        assert r.status_code == 404


# ── POST /rooms/{code}/restart ────────────────────────────────────────────────

class TestRestartGameEndpoint:

    def test_creator_can_restart_returns_204(self):
        mock = make_mock_client(restart_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(
            f"/rooms/{FAKE_ROOM_CODE}/restart",
            json={"requester_id": FAKE_USER_ID, "new_theme": Theme.history.value},
        )
        assert r.status_code == 204
        assert r.content == b""

    def test_passes_new_theme_to_client(self):
        mock = make_mock_client(restart_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        client.post(
            f"/rooms/{FAKE_ROOM_CODE}/restart",
            json={"requester_id": FAKE_USER_ID, "new_theme": Theme.history.value},
        )
        mock.restart_game.assert_awaited_once_with(
            room_code=FAKE_ROOM_CODE,
            requester_id=FAKE_USER_ID,
            new_theme=Theme.history,
        )

    def test_identity_mismatch_returns_403(self):
        mock = make_mock_client(restart_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(
            f"/rooms/{FAKE_ROOM_CODE}/restart",
            json={"requester_id": OTHER_USER_ID, "new_theme": Theme.history.value},
        )
        assert r.status_code == 403
        assert r.json()["error"] == "PERMISSION_DENIED"
        mock.restart_game.assert_not_awaited()

    def test_room_not_finished_returns_409(self):
        mock = make_mock_client(restart_game=FailedPreconditionError("sala ainda em andamento"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(
            f"/rooms/{FAKE_ROOM_CODE}/restart",
            json={"requester_id": FAKE_USER_ID, "new_theme": Theme.history.value},
        )
        assert r.status_code == 409

    def test_invalid_theme_value_returns_400(self):
        mock = make_mock_client(restart_game=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.post(
            f"/rooms/{FAKE_ROOM_CODE}/restart",
            json={"requester_id": FAKE_USER_ID, "new_theme": "tema-que-nao-existe"},
        )
        assert r.status_code == 400