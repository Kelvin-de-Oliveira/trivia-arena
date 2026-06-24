from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # JWT_SECRET / jwt_secret 
    )

    # ------------------------------------------------------------------
    # Game Service — gRPC  
    # ------------------------------------------------------------------
    game_service_grpc_host: str = "game-service"
    game_service_grpc_port: int = 9090

    # ------------------------------------------------------------------
    # Game Service — WebSocket  
    # ------------------------------------------------------------------
    game_service_ws_host: str = "game-service"
    game_service_ws_port: int = 8080

    # ------------------------------------------------------------------
    # User Service — gRPC  
    # ------------------------------------------------------------------
    user_service_grpc_host: str = "user-service"
    user_service_grpc_port: int = 9090

    # ------------------------------------------------------------------
    # JWT  
    # ------------------------------------------------------------------
    jwt_secret: str = "change-me-in-production"
    jwt_expiration_seconds: int = 86400

    # ------------------------------------------------------------------
    # Servidor ASGI  
    # ------------------------------------------------------------------
    port: int = 8000

    # ------------------------------------------------------------------
    # Endereços derivados 
    # ------------------------------------------------------------------

    @property
    def game_grpc_address(self) -> str:
        """host:porta gRPC do Game Service."""
        return f"{self.game_service_grpc_host}:{self.game_service_grpc_port}"

    @property
    def game_ws_url(self) -> str:
        """URL base WebSocket do Game Service (sem path de sala)."""
        return f"ws://{self.game_service_ws_host}:{self.game_service_ws_port}/ws"

    @property
    def user_grpc_address(self) -> str:
        """host:porta gRPC do User Service."""
        return f"{self.user_service_grpc_host}:{self.user_service_grpc_port}"


settings = Settings()