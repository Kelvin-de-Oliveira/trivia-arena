from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _host_from_address(address: str) -> str:
    return address.rsplit(":", 1)[0]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    cors_origins: list[str] = ["http://localhost:5173"]

    # Enderecos completos opcionais. Mantem compatibilidade com .env.prod.example.
    game_grpc_address: str | None = None
    user_grpc_address: str | None = None
    game_ws_url: str | None = None

    # Game Service - gRPC.
    # Defaults locais para rodar o Gateway via uvicorn fora do Docker.
    game_service_grpc_host: str = "localhost"
    game_service_grpc_port: int = 9090

    # Game Service - WebSocket.
    # Se nao for informado, usa o mesmo host do gRPC do Game Service.
    game_service_ws_host: str | None = None
    game_service_ws_port: int = 8080

    # User Service - gRPC.
    user_service_grpc_host: str = "localhost"
    user_service_grpc_port: int = 9091

    # JWT.
    jwt_secret: str = "change-me-in-production"
    jwt_expiration_seconds: int = 86400

    # Servidor ASGI.
    port: int = 8000

    @model_validator(mode="after")
    def derive_service_addresses(self) -> "Settings":
        if not self.game_grpc_address:
            self.game_grpc_address = (
                f"{self.game_service_grpc_host}:{self.game_service_grpc_port}"
            )

        if not self.user_grpc_address:
            self.user_grpc_address = (
                f"{self.user_service_grpc_host}:{self.user_service_grpc_port}"
            )

        if not self.game_ws_url:
            ws_host = self.game_service_ws_host or _host_from_address(
                self.game_grpc_address
            )
            self.game_ws_url = f"ws://{ws_host}:{self.game_service_ws_port}/ws"

        return self


settings = Settings()
