from app.clients.user_service_client import UserServiceClient
from app.exceptions import InvalidArgumentError
from app.schemas.user_schemas import UpdateUserRequest, UserStatsResponse


async def update_user(
    body: UpdateUserRequest,
    user_id: str,
    client: UserServiceClient,
) -> None:
    """
    PUT /users/me
    user_id vem da claim sub do JWT (Depends(get_current_user_id)), nunca
    do corpo da requisição
    """
    if body.name is None and body.password is None:
        raise InvalidArgumentError(
            "é necessário informar ao menos um campo: name ou password"
        )
    await client.update_user(
        user_id=user_id,
        name=body.name,
        password=body.password,
    )


async def get_user_stats(
    user_id: str,
    client: UserServiceClient,
) -> UserStatsResponse:
    """
    GET /users/me/stats
    user_id vem da claim sub do JWT (Depends(get_current_user_id)).
    """
    result = await client.get_user_stats(user_id)
    return UserStatsResponse(
        games_played=result.games_played,
        avg_position=result.avg_position,
        avg_points=result.avg_points,
        highest_score=result.highest_score,
        games_won=result.games_won,
    )