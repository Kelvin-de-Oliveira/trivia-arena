"""
Dependências FastAPI para autenticação JWT.

get_current_user_id  — JWT obrigatório → usado em PUT /users/me e GET /users/me/stats
get_optional_user_id — JWT opcional   → usado em POST /rooms, /join, /start, /restart

Contrato §2.3 (validação do token) e §4 (tabela de rotas com coluna Autenticação).

Nota: a ausência de JWT em get_optional_user_id retorna None (anônimo permitido).
      Um JWT presente mas inválido ainda levanta UnauthenticatedError — a
      opcionalidade é sobre ausência, não sobre validade (§2.3).
"""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_jwt
from app.exceptions import UnauthenticatedError


_bearer = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    """
    JWT obrigatório. Levanta UnauthenticatedError (401) se ausente ou inválido.
    Retorna o user_id extraído da claim sub.
    """
    if credentials is None:
        raise UnauthenticatedError("token não fornecido")
    claims = decode_jwt(credentials.credentials)
    return claims.user_id


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    """
    JWT opcional. Retorna user_id se presente e válido, None se ausente.
    Levanta UnauthenticatedError (401) se o token for fornecido mas inválido.
    """
    if credentials is None:
        return None
    claims = decode_jwt(credentials.credentials)
    return claims.user_id