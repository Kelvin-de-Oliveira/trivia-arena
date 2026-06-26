"""
Validação de app/dependencies/auth_deps.py:
- get_current_user_id: JWT obrigatório
- get_optional_user_id: JWT opcional
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.core.security import create_jwt
from app.dependencies.auth_deps import get_current_user_id, get_optional_user_id
from app.exceptions import UnauthenticatedError
from app.middleware.error_handler import register_exception_handlers


# ── App de teste ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/protected")
    async def protected(user_id: str = Depends(get_current_user_id)):
        return {"user_id": user_id}

    @app.get("/optional")
    async def optional(user_id: str | None = Depends(get_optional_user_id)):
        return {"user_id": user_id}

    return TestClient(app, raise_server_exceptions=False)


def auth_header(user_id: str = "uid-1", name: str = "alice") -> dict:
    token = create_jwt(user_id, name)
    return {"Authorization": f"Bearer {token}"}


# ── get_current_user_id ───────────────────────────────────────────────────────

class TestGetCurrentUserId:

    def test_valid_token_returns_user_id(self, client):
        r = client.get("/protected", headers=auth_header("uid-1"))
        assert r.status_code == 200
        assert r.json()["user_id"] == "uid-1"

    def test_missing_token_returns_401(self, client):
        r = client.get("/protected")
        assert r.status_code == 401

    def test_missing_token_error_code(self, client):
        r = client.get("/protected")
        assert r.json()["error"] == "UNAUTHENTICATED"

    def test_invalid_token_returns_401(self, client):
        r = client.get("/protected", headers={"Authorization": "Bearer token.invalido"})
        assert r.status_code == 401

    def test_invalid_token_error_code(self, client):
        r = client.get("/protected", headers={"Authorization": "Bearer token.invalido"})
        assert r.json()["error"] == "UNAUTHENTICATED"

    def test_malformed_header_returns_401(self, client):
        # header sem "Bearer " prefix
        r = client.get("/protected", headers={"Authorization": "token-sem-bearer"})
        assert r.status_code == 401


# ── get_optional_user_id ──────────────────────────────────────────────────────

class TestGetOptionalUserId:

    def test_valid_token_returns_user_id(self, client):
        r = client.get("/optional", headers=auth_header("uid-2"))
        assert r.status_code == 200
        assert r.json()["user_id"] == "uid-2"

    def test_missing_token_returns_none(self, client):
        r = client.get("/optional")
        assert r.status_code == 200
        assert r.json()["user_id"] is None

    def test_invalid_token_returns_401(self, client):
        """Token presente mas inválido ainda levanta 401 — opcionalidade é sobre ausência."""
        r = client.get("/optional", headers={"Authorization": "Bearer token.invalido"})
        assert r.status_code == 401

    def test_invalid_token_error_code(self, client):
        r = client.get("/optional", headers={"Authorization": "Bearer token.invalido"})
        assert r.json()["error"] == "UNAUTHENTICATED"