"""
Fluxo testado: HTTP → router → user_service → (UserServiceClient mockado).

Usa dependency_overrides para:
  - injetar um UserServiceClient mockado (sem gRPC real)
  - simular usuário autenticado sobrescrevendo get_current_user_id
    diretamente (sem precisar gerar um JWT real)

O caminho "sem token" NÃO é mockado: exercita o get_current_user_id real
(credentials is None → UnauthenticatedError), que já é coberto em detalhe
por tests/unit/test_auth_deps.py, aqui só confirmamos que o router está
de fato protegido por essa dependency, sem precisar validar JWT de verdade.

Referência: https://fastapi.tiangolo.com/advanced/testing-dependencies/
"""

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rest import users
from app.clients.user_service_client import UserServiceClient, UserStatsResult
from app.dependencies.auth_deps import get_current_user_id
from app.dependencies.grpc_deps import get_user_client
from app.exceptions import AlreadyExistsError, NotFoundError, UpstreamUnavailableError
from app.middleware.error_handler import register_exception_handlers

FAKE_USER_ID = "uuid-fake-1"

_NO_OVERRIDE = object() 


def build_test_app(mock_client: UserServiceClient, jwt_user_id=_NO_OVERRIDE) -> FastAPI:
    """
    App mínimo com apenas o router de users.

    jwt_user_id:
        _NO_OVERRIDE -> não sobrescreve get_current_user_id (sem token = 401 real)
        "algum-id"   -> força usuário autenticado com esse user_id (sub do JWT)
    """
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(users.router)
    app.dependency_overrides[get_user_client] = lambda: mock_client
    if jwt_user_id is not _NO_OVERRIDE:
        app.dependency_overrides[get_current_user_id] = lambda: jwt_user_id
    return app


def make_mock_client(**method_results) -> UserServiceClient:
    """
    method_results: nome_do_metodo=valor_de_retorno, ou uma instância de
    Exception para simular o client levantando erro (side_effect).
    """
    client = AsyncMock(spec=UserServiceClient)
    for method_name, result in method_results.items():
        mock_method = getattr(client, method_name)
        if isinstance(result, Exception):
            mock_method.side_effect = result
        else:
            mock_method.return_value = result
    return client


def make_stats(**overrides) -> UserStatsResult:
    defaults = dict(
        games_played=10,
        avg_position=2.5,
        avg_points=42.0,
        highest_score=100,
        games_won=3,
    )
    defaults.update(overrides)
    return UserStatsResult(**defaults)


# ── PUT /users/me ──────────────────────────────────────────────────────────────

class TestUpdateUserEndpoint:

    def test_update_name_only_returns_204(self):
        mock = make_mock_client(update_user=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.put("/users/me", json={"name": "novo_nome"})
        assert r.status_code == 204
        assert r.content == b""

    def test_update_password_only_returns_204(self):
        mock = make_mock_client(update_user=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.put("/users/me", json={"password": "nova_senha"})
        assert r.status_code == 204

    def test_passes_user_id_from_jwt_not_from_body(self):
        mock = make_mock_client(update_user=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        client.put("/users/me", json={"name": "novo_nome"})
        mock.update_user.assert_awaited_once_with(
            user_id=FAKE_USER_ID,
            name="novo_nome",
            password=None,
        )

    def test_no_fields_returns_400(self):
        mock = make_mock_client(update_user=True)
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.put("/users/me", json={})
        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_ARGUMENT"
        mock.update_user.assert_not_awaited()

    def test_name_already_in_use_returns_409(self):
        mock = make_mock_client(update_user=AlreadyExistsError("nome já em uso"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.put("/users/me", json={"name": "existente"})
        assert r.status_code == 409
        assert r.json()["error"] == "ALREADY_EXISTS"

    def test_missing_token_returns_401(self):
        mock = make_mock_client(update_user=True)
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)  # sem override de auth
        r = client.put("/users/me", json={"name": "novo_nome"})
        assert r.status_code == 401
        assert r.json()["error"] == "UNAUTHENTICATED"
        mock.update_user.assert_not_awaited()

    def test_upstream_unavailable_returns_503(self):
        mock = make_mock_client(update_user=UpstreamUnavailableError("user service indisponível"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.put("/users/me", json={"name": "novo_nome"})
        assert r.status_code == 503


# ── GET /users/me/stats ────────────────────────────────────────────────────────

class TestGetUserStatsEndpoint:

    def test_returns_200_with_stats(self):
        mock = make_mock_client(get_user_stats=make_stats())
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.get("/users/me/stats")
        assert r.status_code == 200
        assert r.json() == {
            "games_played": 10,
            "avg_position": 2.5,
            "avg_points": 42.0,
            "highest_score": 100,
            "games_won": 3,
        }

    def test_passes_user_id_from_jwt(self):
        mock = make_mock_client(get_user_stats=make_stats())
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        client.get("/users/me/stats")
        mock.get_user_stats.assert_awaited_once_with(FAKE_USER_ID)

    def test_user_not_found_returns_404(self):
        mock = make_mock_client(get_user_stats=NotFoundError("usuário não encontrado"))
        client = TestClient(build_test_app(mock, jwt_user_id=FAKE_USER_ID), raise_server_exceptions=False)
        r = client.get("/users/me/stats")
        assert r.status_code == 404
        assert r.json()["error"] == "NOT_FOUND"

    def test_missing_token_returns_401(self):
        mock = make_mock_client(get_user_stats=make_stats())
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)  # sem override de auth
        r = client.get("/users/me/stats")
        assert r.status_code == 401
        mock.get_user_stats.assert_not_awaited()