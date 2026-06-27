""" Rotas de autenticação """

from fastapi import APIRouter, Depends

from app.dependencies.grpc_deps import get_user_client
from app.clients.user_service_client import UserServiceClient
from app.schemas.auth_schemas import AuthResponse, LoginRequest, RegisterRequest
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    user_client: UserServiceClient = Depends(get_user_client),
) -> AuthResponse:
    return await auth_service.register(
        name=body.name,
        password=body.password,
        user_client=user_client,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    user_client: UserServiceClient = Depends(get_user_client),
) -> AuthResponse:
    return await auth_service.login(
        name=body.name,
        password=body.password,
        user_client=user_client,
    )