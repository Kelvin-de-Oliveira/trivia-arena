"""
Emissão e validação de JWT do API Gateway.

Contrato §2.1 — Claims:   sub (user_id), name, iat, exp
Contrato §2.2 — Algoritmo: HS256, segredo JWT_SECRET, expiração JWT_EXPIRATION_SECONDS
Contrato §2.3 — Validação: token ausente ou inválido → UnauthenticatedError

Não há refresh token: ao expirar, o cliente deve autenticar-se novamente.
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import jwt

from app.core.config import settings
from app.exceptions import UnauthenticatedError


@dataclass(frozen=True)
class Claims:
    """Dados extraídos do JWT após validação bem-sucedida."""
    user_id: str 
    name: str


def create_jwt(user_id: str, name: str) -> str:
    """
    Assina e retorna um JWT com as claims do contrato §2.1.
    Chamado pelo auth_service após RegisterUser/LoginUser no User Service.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "name": name,
        "iat": now,
        "exp": now.timestamp() + settings.jwt_expiration_seconds,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_jwt(token: str) -> Claims:
    """
    Valida assinatura e expiração do token e retorna as Claims.
    Levanta UnauthenticatedError para qualquer falha.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
        )
        return Claims(user_id=payload["sub"], name=payload["name"])
    except jwt.ExpiredSignatureError:
        raise UnauthenticatedError("token expirado")
    except jwt.InvalidTokenError:
        raise UnauthenticatedError("token inválido")