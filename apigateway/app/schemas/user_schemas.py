"""
DTOs de perfil e estatísticas do usuário.
Rotas: PUT /users/me, GET /users/me/stats.

user_id não consta no corpo de UpdateUserRequest: vem da claim
sub do JWT, nunca do cliente.

A regra "ao menos um campo obrigatório" é aplicada na camada de
serviço (services/user_service.py), que lança InvalidArgumentError
mapeada para 400, coerente com o documento de contrato.
"""

from pydantic import BaseModel


class UpdateUserRequest(BaseModel):
    name:     str | None = None
    password: str | None = None


class UserStatsResponse(BaseModel):
    games_played:  int
    avg_position:  float
    avg_points:    float
    highest_score: int
    games_won:     int