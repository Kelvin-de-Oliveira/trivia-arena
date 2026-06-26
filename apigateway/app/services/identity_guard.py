"""
Garantia de integridade de identidade do jogador.

Regras aplicadas por ensure_identity():

JWT presente (autenticado):
    jwt_user_id é a identidade autoritativa. Se divergir do
    client_provided_id, rejeita com PermissionDeniedError (403).
    O WebSocket handler  captura PermissionDeniedError e
    envia o frame error com code: PLAYER_ID_MISMATCH 

Sem JWT (anônimo):
    Repassa client_provided_id sem alteração.
    Formato obrigatório: anon:{uuid v4}.
    Formato inválido → InvalidArgumentError (400).
"""

import re

from app.exceptions import InvalidArgumentError, PermissionDeniedError


_ANON_PATTERN = re.compile(
    r"^anon:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def ensure_identity(jwt_user_id: str | None, client_provided_id: str) -> str:
    """
    Valida a identidade do jogador 

    Args:
        jwt_user_id:        user_id extraído da claim sub do JWT,
                            ou None se a requisição for anônima.
        client_provided_id: valor enviado pelo cliente no corpo da
                            requisição (creator_id, player_id, requester_id)
                            ou no header player-id (WebSocket).

    Returns:
        client_provided_id validado - pronto para repassar ao serviço interno.

    Raises:
        PermissionDeniedError: JWT presente e diverge do client_provided_id
        InvalidArgumentError:  Anônimo com formato inválido 
    """
    if jwt_user_id is not None:
        #autenticado
        if jwt_user_id != client_provided_id:
            raise PermissionDeniedError(
                f"identidade diverge do JWT: esperado '{jwt_user_id}'"
            )
        return client_provided_id

    #anônimo
    if not _ANON_PATTERN.match(client_provided_id):
        raise InvalidArgumentError(
            "player_id anônimo deve seguir o formato anon:{uuid}, "
            f"recebido: '{client_provided_id}'"
        )
    return client_provided_id