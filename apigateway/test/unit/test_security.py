"""
Validação dos artefatos de app/core/security.py:
- Emissão e validação de JWT
- Claims corretas no roundtrip
- Token expirado → UnauthenticatedError("token expirado")
- Token inválido → UnauthenticatedError("token inválido")
"""

import jwt
import pytest

from app.core.config import settings
from app.core.security import Claims, create_jwt, decode_jwt
from app.exceptions import UnauthenticatedError


class TestSecurity:

    # ── Roundtrip ─────────────────────────────────────────────────────────

    def test_roundtrip_user_id(self):
        token = create_jwt("uid-1", "alice")
        claims = decode_jwt(token)
        assert claims.user_id == "uid-1"

    def test_roundtrip_name(self):
        token = create_jwt("uid-1", "alice")
        claims = decode_jwt(token)
        assert claims.name == "alice"

    def test_roundtrip_returns_claims(self):
        token = create_jwt("uid-1", "alice")
        claims = decode_jwt(token)
        assert isinstance(claims, Claims)

    # ── Token expirado ────────────────────────────────────────────────────

    def test_expired_token_raises(self):
        payload = {"sub": "uid-1", "name": "alice", "iat": 0, "exp": 1}
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        with pytest.raises(UnauthenticatedError):
            decode_jwt(token)

    def test_expired_token_message(self):
        payload = {"sub": "uid-1", "name": "alice", "iat": 0, "exp": 1}
        token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
        with pytest.raises(UnauthenticatedError) as exc_info:
            decode_jwt(token)
        assert exc_info.value.message == "token expirado"

    # ── Token inválido ────────────────────────────────────────────────────

    def test_invalid_token_raises(self):
        with pytest.raises(UnauthenticatedError):
            decode_jwt("token.invalido.qualquer")

    def test_invalid_token_message(self):
        with pytest.raises(UnauthenticatedError) as exc_info:
            decode_jwt("token.invalido.qualquer")
        assert exc_info.value.message == "token inválido"

    def test_empty_string_raises(self):
        with pytest.raises(UnauthenticatedError):
            decode_jwt("")

    def test_wrong_secret_raises(self):
        token = jwt.encode(
            {"sub": "uid-1", "name": "alice"},
            "segredo-errado-com-mais-de-32-caracteres",
            algorithm="HS256",
        )
        with pytest.raises(UnauthenticatedError):
            decode_jwt(token)

    def test_wrong_secret_message(self):
        token = jwt.encode(
            {"sub": "uid-1", "name": "alice"},
            "segredo-errado-com-mais-de-32-caracteres",
            algorithm="HS256",
        )
        with pytest.raises(UnauthenticatedError) as exc_info:
            decode_jwt(token)
        assert exc_info.value.message == "token inválido"

    # ── Claims imutáveis ──────────────────────────────────────────────────

    def test_claims_are_frozen(self):
        token = create_jwt("uid-1", "alice")
        claims = decode_jwt(token)
        with pytest.raises(Exception):
            claims.user_id = "outro"  # type: ignore