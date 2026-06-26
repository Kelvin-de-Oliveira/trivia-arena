"""
Cliente gRPC do User Service.

Responsabilidades:
- Encapsular os stubs gerados em app/clients/generated/
- Converter grpc.RpcError em exceção de domínio via error_mapper
- Retornar dataclasses Python ao chamador, a camada de serviço
  não conhece detalhes de gRPC
"""

from dataclasses import dataclass

import grpc.aio

from app.clients.generated import user_pb2, user_pb2_grpc
from app.mappers.error_mapper import grpc_error_to_exception


# ── Tipos de retorno ──────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AuthResult:
    user_id: str
    name: str


@dataclass(frozen=True)
class UserStatsResult:
    games_played:  int
    avg_position:  float
    avg_points:    float
    highest_score: int
    games_won:     int


# ── Cliente ───────────────────────────────────────────────────────────────────

class UserServiceClient:

    def __init__(self, channel: grpc.aio.Channel) -> None:
        self._stub = user_pb2_grpc.UserServiceStub(channel)

    async def register_user(self, name: str, password: str) -> AuthResult:
        try:
            r = await self._stub.RegisterUser(
                user_pb2.RegisterUserRequest(name=name, password=password)
            )
            return AuthResult(user_id=r.user_id, name=r.name)
        except grpc.RpcError as e:
            raise grpc_error_to_exception(e)

    async def login_user(self, name: str, password: str) -> AuthResult:
        try:
            r = await self._stub.LoginUser(
                user_pb2.LoginUserRequest(name=name, password=password)
            )
            return AuthResult(user_id=r.user_id, name=r.name)
        except grpc.RpcError as e:
            raise grpc_error_to_exception(e)

    async def update_user(
        self,
        user_id: str,
        name: str | None = None,
        password: str | None = None,
    ) -> bool:
        
        #UpdateUser ao menos um campo obrigatório 
        #A validação é feita na camada de serviço antes de chegar aqui.
        
        try:
            kwargs: dict = {"user_id": user_id}
            if name is not None:
                kwargs["name"] = name
            if password is not None:
                kwargs["password"] = password

            r = await self._stub.UpdateUser(
                user_pb2.UpdateUserRequest(**kwargs)
            )
            return r.success
        except grpc.RpcError as e:
            raise grpc_error_to_exception(e)

    async def get_user_stats(self, user_id: str) -> UserStatsResult:
        try:
            r = await self._stub.GetUserStats(
                user_pb2.GetUserStatsRequest(user_id=user_id)
            )
            return UserStatsResult(
                games_played=r.games_played,
                avg_position=r.avg_position,
                avg_points=r.avg_points,
                highest_score=r.highest_score,
                games_won=r.games_won,
            )
        except grpc.RpcError as e:
            raise grpc_error_to_exception(e)