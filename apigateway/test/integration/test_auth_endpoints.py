"""
Fluxo testado: HTTP → router → auth_service → (UserServiceClient mockado).
Usa dependency_overrides para injetar cliente mockado sem gRPC real.
Referência: https://fastapi.tiangolo.com/advanced/testing-dependencies/
"""

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.rest import auth
from app.clients.user_service_client import AuthResult, UserServiceClient
from app.core.security import decode_jwt
from app.dependencies.grpc_deps import get_user_client
from app.exceptions import AlreadyExistsError, UnauthenticatedError
from app.middleware.error_handler import register_exception_handlers

FAKE_USER_ID = "uuid-fake-1"
FAKE_NAME = "alice"


def build_test_app(mock_client: UserServiceClient) -> FastAPI:
    """App mínimo com apenas o router de auth e dependency override."""
    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(auth.router)
    app.dependency_overrides[get_user_client] = lambda: mock_client
    return app


def make_mock_client(
    register_result=None,
    login_result=None,
) -> UserServiceClient:
    client = AsyncMock(spec=UserServiceClient)
    if isinstance(register_result, Exception):
        client.register_user.side_effect = register_result
    elif register_result is not None:
        client.register_user.return_value = register_result
    if isinstance(login_result, Exception):
        client.login_user.side_effect = login_result
    elif login_result is not None:
        client.login_user.return_value = login_result
    return client


# ── POST /auth/register ───────────────────────────────────────────────────────

class TestRegisterEndpoint:

    @pytest.fixture()
    def client(self):
        mock = make_mock_client(
            register_result=AuthResult(user_id=FAKE_USER_ID, name=FAKE_NAME)
        )
        return TestClient(build_test_app(mock), raise_server_exceptions=False)

    def test_returns_201(self, client):
        r = client.post("/auth/register", json={"name": "alice", "password": "secret"})
        assert r.status_code == 201

    def test_response_has_jwt(self, client):
        r = client.post("/auth/register", json={"name": "alice", "password": "secret"})
        assert "jwt" in r.json()

    def test_response_has_user_id(self, client):
        r = client.post("/auth/register", json={"name": "alice", "password": "secret"})
        assert r.json()["user_id"] == FAKE_USER_ID

    def test_jwt_claims_are_correct(self, client):
        r = client.post("/auth/register", json={"name": "alice", "password": "secret"})
        claims = decode_jwt(r.json()["jwt"])
        assert claims.user_id == FAKE_USER_ID
        assert claims.name == FAKE_NAME

    def test_conflict_returns_409(self):
        mock = make_mock_client(
            register_result=AlreadyExistsError("nome já cadastrado")
        )
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.post("/auth/register", json={"name": "existente", "password": "secret"})
        assert r.status_code == 409

    def test_conflict_error_code(self):
        mock = make_mock_client(
            register_result=AlreadyExistsError("nome já cadastrado")
        )
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.post("/auth/register", json={"name": "existente", "password": "secret"})
        assert r.json()["error"] == "ALREADY_EXISTS"
    
    def test_missing_fields_returns_400(self, client):
        r = client.post("/auth/register", json={})
        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_ARGUMENT"


# ── POST /auth/login ──────────────────────────────────────────────────────────

class TestLoginEndpoint:

    @pytest.fixture()
    def client(self):
        mock = make_mock_client(
            login_result=AuthResult(user_id=FAKE_USER_ID, name=FAKE_NAME)
        )
        return TestClient(build_test_app(mock), raise_server_exceptions=False)

    def test_returns_200(self, client):
        r = client.post("/auth/login", json={"name": "alice", "password": "correta"})
        assert r.status_code == 200

    def test_response_has_jwt(self, client):
        r = client.post("/auth/login", json={"name": "alice", "password": "correta"})
        assert "jwt" in r.json()

    def test_response_has_user_id(self, client):
        r = client.post("/auth/login", json={"name": "alice", "password": "correta"})
        assert r.json()["user_id"] == FAKE_USER_ID

    def test_jwt_claims_are_correct(self, client):
        r = client.post("/auth/login", json={"name": "alice", "password": "correta"})
        claims = decode_jwt(r.json()["jwt"])
        assert claims.user_id == FAKE_USER_ID
        assert claims.name == FAKE_NAME

    def test_invalid_credentials_returns_401(self):
        mock = make_mock_client(
            login_result=UnauthenticatedError("credenciais inválidas")
        )
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.post("/auth/login", json={"name": "alice", "password": "errada"})
        assert r.status_code == 401

    def test_invalid_credentials_error_code(self):
        mock = make_mock_client(
            login_result=UnauthenticatedError("credenciais inválidas")
        )
        client = TestClient(build_test_app(mock), raise_server_exceptions=False)
        r = client.post("/auth/login", json={"name": "alice", "password": "errada"})
        assert r.json()["error"] == "UNAUTHENTICATED"