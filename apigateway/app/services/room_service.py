from app.clients.game_service_client import GameServiceClient
from app.schemas.room_schemas import (
    CreateRoomRequest,
    CreateRoomResponse,
    GetRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    RestartGameRequest,
    StartGameRequest,
)
from app.services.identity_guard import ensure_identity


async def create_room(
    body: CreateRoomRequest,
    jwt_user_id: str | None,
    client: GameServiceClient,
) -> CreateRoomResponse:
    """
    POST /rooms
    Aplica ensure_identity sobre creator_id  antes de criar a sala.
    """
    creator_id = ensure_identity(jwt_user_id, body.creator_id)
    room_code = await client.create_room(
        creator_id=creator_id,
        creator_name=body.creator_name,
        is_anonymous=body.is_anonymous,
        max_players=body.max_players,
        num_questions=body.num_questions,
        theme=body.theme,
    )
    return CreateRoomResponse(room_code=room_code)


async def join_room(
    room_code: str,
    body: JoinRoomRequest,
    jwt_user_id: str | None,
    client: GameServiceClient,
) -> JoinRoomResponse:
    """
    POST /rooms/{code}/join
    Aplica ensure_identity sobre player_id  antes de entrar na sala.
    room_code vem do path, não do body 
    """
    player_id = ensure_identity(jwt_user_id, body.player_id)
    return await client.join_room(
        room_code=room_code,
        player_id=player_id,
        player_name=body.player_name,
        is_anonymous=body.is_anonymous,
    )


async def get_room(
    room_code: str,
    client: GameServiceClient,
) -> GetRoomResponse:
    """
    GET /rooms/{code}
    Sem autenticação e sem campo de identidade  consulta direta.
    """
    return await client.get_room(room_code=room_code)


async def start_game(
    room_code: str,
    body: StartGameRequest,
    jwt_user_id: str | None,
    client: GameServiceClient,
) -> bool:
    """
    POST /rooms/{code}/start
    Aplica ensure_identity sobre requester_id antes de iniciar a partida.
    Retorna bool vindo do Game Service; o router constrói StartGameResponse.
    """
    requester_id = ensure_identity(jwt_user_id, body.requester_id)
    return await client.start_game(
        room_code=room_code,
        requester_id=requester_id,
    )


async def restart_game(
    room_code: str,
    body: RestartGameRequest,
    jwt_user_id: str | None,
    client: GameServiceClient,
) -> None:
    """
    POST /rooms/{code}/restart
    Aplica ensure_identity sobre requester_id  antes de reiniciar.
    Sem corpo de resposta — falhas chegam como exceção via error_mapper.
    """
    requester_id = ensure_identity(jwt_user_id, body.requester_id)
    await client.restart_game(
        room_code=room_code,
        requester_id=requester_id,
        new_theme=body.new_theme,
    )