"""
Hierarquia de exceções de domínio do API Gateway.

Cada classe carrega o HTTP status code e o error code que serão usados
pelo error_handler (middleware) para montar o ErrorResponse

Tabela canônica :
    INVALID_ARGUMENT    → 400
    UNAUTHENTICATED     → 401
    PERMISSION_DENIED   → 403
    NOT_FOUND           → 404
    ALREADY_EXISTS      → 409
    FAILED_PRECONDITION → 409
    UNAVAILABLE         → 503

PlayerIdMismatchError é subclasse de PermissionDeniedError:
- via REST   → HTTP 403 / PERMISSION_DENIED 
- via WS     → frame error com code PLAYER_ID_MISMATCH 
  O handler de WebSocket trata esse caso separadamente.
"""


class GatewayError(Exception):
    """Base de todas as exceções de domínio do Gateway."""
    status_code: int
    error_code: str

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidArgumentError(GatewayError):
    status_code = 400
    error_code  = "INVALID_ARGUMENT"


class UnauthenticatedError(GatewayError):
    status_code = 401
    error_code  = "UNAUTHENTICATED"


class PermissionDeniedError(GatewayError):
    status_code = 403
    error_code  = "PERMISSION_DENIED"


class PlayerIdMismatchError(PermissionDeniedError):
    """Identidade JWT diverge do campo de identidade do cliente"""
    error_code = "PLAYER_ID_MISMATCH"


class NotFoundError(GatewayError):
    status_code = 404
    error_code  = "NOT_FOUND"


class AlreadyExistsError(GatewayError):
    status_code = 409
    error_code  = "ALREADY_EXISTS"


class FailedPreconditionError(GatewayError):
    status_code = 409
    error_code  = "FAILED_PRECONDITION"


class UpstreamUnavailableError(GatewayError):
    status_code = 503
    error_code  = "UNAVAILABLE"