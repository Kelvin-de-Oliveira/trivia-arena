from fastapi import APIRouter, Depends, status

import app.services.user_service as user_service
from app.clients.user_service_client import UserServiceClient
from app.dependencies.auth_deps import get_current_user_id
from app.dependencies.grpc_deps import get_user_client
from app.schemas.user_schemas import UpdateUserRequest, UserStatsResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.put("/me", status_code=status.HTTP_204_NO_CONTENT)
async def update_user(
    body: UpdateUserRequest,
    user_id: str = Depends(get_current_user_id),
    client: UserServiceClient = Depends(get_user_client),
) -> None:
    """
    PUT /users/me  atualiza nome e/ou senha do usuário autenticado.
    JWT obrigatório; user_id vem da claim sub, nunca do corpo.
    """
    await user_service.update_user(body, user_id, client)


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_user_stats(
    user_id: str = Depends(get_current_user_id),
    client: UserServiceClient = Depends(get_user_client),
) -> UserStatsResponse:
    """
    GET /users/me/stats  estatísticas históricas do usuário autenticado.
    JWT obrigatório.
    """
    return await user_service.get_user_stats(user_id, client)