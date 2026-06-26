from app.clients.user_service_client import UserServiceClient
from app.core.security import create_jwt
from app.schemas.auth_schemas import AuthResponse


async def register(
    name: str,
    password: str,
    user_client: UserServiceClient,
) -> AuthResponse:
    """
    registra novo usuário e retorna JWT assinado.
    """
    result = await user_client.register_user(name, password)
    token = create_jwt(result.user_id, result.name)
    return AuthResponse(jwt=token, user_id=result.user_id)


async def login(
    name: str,
    password: str,
    user_client: UserServiceClient,
) -> AuthResponse:
    """
    autentica usuário existente e retorna JWT assinado.
    """
    result = await user_client.login_user(name, password)
    token = create_jwt(result.user_id, result.name)
    return AuthResponse(jwt=token, user_id=result.user_id)