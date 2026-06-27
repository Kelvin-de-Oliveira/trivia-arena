from fastapi import APIRouter, Depends, status

import app.services.room_service as room_service
from app.clients.game_service_client import GameServiceClient
from app.dependencies.auth_deps import get_optional_user_id
from app.dependencies.grpc_deps import get_game_client
from app.schemas.room_schemas import (
    CreateRoomRequest,
    CreateRoomResponse,
    GetRoomResponse,
    JoinRoomRequest,
    JoinRoomResponse,
    RestartGameRequest,
    StartGameRequest,
    StartGameResponse,
)

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CreateRoomResponse)
async def create_room(
    body: CreateRoomRequest,
    jwt_user_id: str | None = Depends(get_optional_user_id),
    client: GameServiceClient = Depends(get_game_client),
) -> CreateRoomResponse:
    """
    POST /rooms  cria uma nova sala.
    Autenticação opcional: se JWT presente, creator_id deve coincidir com sub
    """
    return await room_service.create_room(body, jwt_user_id, client)


@router.post("/{code}/join", response_model=JoinRoomResponse)
async def join_room(
    code: str,
    body: JoinRoomRequest,
    jwt_user_id: str | None = Depends(get_optional_user_id),
    client: GameServiceClient = Depends(get_game_client),
) -> JoinRoomResponse:
    """
    POST /rooms/{code}/join  entra em uma sala existente.
    Autenticação opcional: se JWT presente, player_id deve coincidir com sub 
    """
    return await room_service.join_room(code, body, jwt_user_id, client)


@router.get("/{code}", response_model=GetRoomResponse)
async def get_room(
    code: str,
    client: GameServiceClient = Depends(get_game_client),
) -> GetRoomResponse:
    """
    GET /rooms/{code}  consulta estado atual da sala.
    Sem autenticação e sem campo de identidade 
    """
    return await room_service.get_room(code, client)


@router.post("/{code}/start", response_model=StartGameResponse)
async def start_game(
    code: str,
    body: StartGameRequest,
    jwt_user_id: str | None = Depends(get_optional_user_id),
    client: GameServiceClient = Depends(get_game_client),
) -> StartGameResponse:
    """
    POST /rooms/{code}/start  inicia a partida.
    Autenticação opcional: se JWT presente, requester_id deve coincidir com sub 
    """
    started = await room_service.start_game(code, body, jwt_user_id, client)
    return StartGameResponse(started=started)


@router.post("/{code}/restart", status_code=status.HTTP_204_NO_CONTENT)
async def restart_game(
    code: str,
    body: RestartGameRequest,
    jwt_user_id: str | None = Depends(get_optional_user_id),
    client: GameServiceClient = Depends(get_game_client),
) -> None:
    """
    POST /rooms/{code}/restart reinicia a partida com novo tema.
    Autenticação opcional se JWT presente, requester_id deve coincidir com sub 
    Sem corpo de resposta  falhas chegam como exceção via error_mapper.
    """
    await room_service.restart_game(code, body, jwt_user_id, client)