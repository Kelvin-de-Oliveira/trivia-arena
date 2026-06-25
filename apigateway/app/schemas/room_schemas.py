"""
DTOs de sala e partida.
Rotas: POST /rooms, POST /rooms/{code}/join, GET /rooms/{code},
       POST /rooms/{code}/start, POST /rooms/{code}/restart.

room_code não consta nos corpos de request pois vem do path parameter;
o Gateway o injeta na chamada gRPC.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Theme(str, Enum):
    """Temas válidos conforme contrato Game Service"""
    music               = "music"
    sport_and_leisure   = "sport_and_leisure"
    film_and_tv         = "film_and_tv"
    arts_and_literature = "arts_and_literature"
    history             = "history"
    society_and_culture = "society_and_culture"
    science             = "science"
    geography           = "geography"
    food_and_drink      = "food_and_drink"
    general_knowledge   = "general_knowledge"


class RoomStatus(str, Enum):
    """Espelha o enum RoomStatus do proto"""
    WAITING     = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    FINISHED    = "FINISHED"


class PlayerSchema(BaseModel):
    player_id:   str
    player_name: str
    is_anonymous: bool
    score:       int


# ── criar sala ────────────────────────────────────────────────────────────

class CreateRoomRequest(BaseModel):
    creator_id:    str
    creator_name:  str
    is_anonymous:  bool
    max_players:   int = Field(ge=2, le=10)
    num_questions: int = Field(ge=5, le=20)
    theme:         Theme


class CreateRoomResponse(BaseModel):
    room_code: str


# ──entrar na sala ────────────────────────────────────────────────────────

class JoinRoomRequest(BaseModel):
    player_id:   str
    player_name: str
    is_anonymous: bool


class JoinRoomResponse(BaseModel):
    players:      list[PlayerSchema]
    status:       RoomStatus
    theme:        Theme
    max_players:  int
    creator_id:   str
    num_questions: int


# ── consultar sala ────────────────────────────────────────────────────────

class GetRoomResponse(BaseModel):
    room_code:    str
    status:       RoomStatus
    theme:        Theme
    max_players:  int
    num_questions: int
    players:      list[PlayerSchema]
    creator_id:   str


# ──iniciar partida ───────────────────────────────────────────────────────

class StartGameRequest(BaseModel):
    requester_id: str


class StartGameResponse(BaseModel):
    started: bool


# ── reiniciar partida ─────────────────────────────────────────────────────

class RestartGameRequest(BaseModel):
    requester_id: str
    new_theme:    Theme