"""
Validação dos seguinte artefatos :
- schemas: validação de entrada e formato de saída
- exceptions: hierarquia, status codes e error codes
- mappers: gRPC StatusCode → exceção de domínio
- middleware: exceção de domínio → JSONResponse 
"""

import grpc
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.exceptions import (
    AlreadyExistsError,
    FailedPreconditionError,
    GatewayError,
    InvalidArgumentError,
    NotFoundError,
    PermissionDeniedError,
    PlayerIdMismatchError,
    UnauthenticatedError,
    UpstreamUnavailableError,
)
from app.mappers.error_mapper import grpc_error_to_exception
from app.middleware.error_handler import register_exception_handlers
from app.schemas.auth_schemas import AuthResponse, LoginRequest, RegisterRequest
from app.schemas.error_schemas import ErrorResponse
from app.schemas.room_schemas import (
    CreateRoomRequest,
    RestartGameRequest,
    RoomStatus,
    Theme,
)
from app.schemas.user_schemas import UpdateUserRequest, UserStatsResponse


# ── Schemas ───────────────────────────────────────────────────────────────

class TestAuthSchemas:
    def test_register_request_valid(self):
        r = RegisterRequest(name="alice", password="secret")
        assert r.name == "alice"

    def test_login_request_valid(self):
        r = LoginRequest(name="alice", password="secret")
        assert r.name == "alice"

    def test_auth_response_fields(self):
        r = AuthResponse(jwt="token.abc", user_id="uuid-1")
        assert r.jwt == "token.abc"
        assert r.user_id == "uuid-1"


class TestRoomSchemas:
    def test_create_room_valid(self):
        r = CreateRoomRequest(
            creator_id="uuid-1",
            creator_name="alice",
            is_anonymous=False,
            max_players=4,
            num_questions=10,
            theme=Theme.science,
        )
        assert r.theme == Theme.science

    def test_create_room_max_players_below_min(self):
        with pytest.raises(ValidationError):
            CreateRoomRequest(
                creator_id="uuid-1", creator_name="alice", is_anonymous=False,
                max_players=1, num_questions=10, theme=Theme.science,
            )

    def test_create_room_max_players_above_max(self):
        with pytest.raises(ValidationError):
            CreateRoomRequest(
                creator_id="uuid-1", creator_name="alice", is_anonymous=False,
                max_players=11, num_questions=10, theme=Theme.science,
            )

    def test_create_room_num_questions_below_min(self):
        with pytest.raises(ValidationError):
            CreateRoomRequest(
                creator_id="uuid-1", creator_name="alice", is_anonymous=False,
                max_players=4, num_questions=4, theme=Theme.science,
            )

    def test_create_room_invalid_theme(self):
        with pytest.raises(ValidationError):
            CreateRoomRequest(
                creator_id="uuid-1", creator_name="alice", is_anonymous=False,
                max_players=4, num_questions=10, theme="invalid_theme",
            )

    def test_restart_game_valid(self):
        r = RestartGameRequest(requester_id="uuid-1", new_theme=Theme.history)
        assert r.new_theme == Theme.history

    def test_room_status_values(self):
        assert RoomStatus.WAITING == "WAITING"
        assert RoomStatus.IN_PROGRESS == "IN_PROGRESS"
        assert RoomStatus.FINISHED == "FINISHED"

    def test_all_themes_valid(self):
        expected = {
            "music", "sport_and_leisure", "film_and_tv", "arts_and_literature",
            "history", "society_and_culture", "science", "geography",
            "food_and_drink", "general_knowledge",
        }
        assert {t.value for t in Theme} == expected
    def test_create_room_max_players_min_boundary(self):
        r = CreateRoomRequest(
            creator_id="uuid-1", creator_name="alice", is_anonymous=False,
            max_players=2, num_questions=5, theme=Theme.science,
        )
        assert r.max_players == 2

    def test_create_room_max_players_max_boundary(self):
        r = CreateRoomRequest(
            creator_id="uuid-1", creator_name="alice", is_anonymous=False,
            max_players=10, num_questions=5, theme=Theme.science,
        )
        assert r.max_players == 10

    def test_create_room_num_questions_min_boundary(self):
        r = CreateRoomRequest(
            creator_id="uuid-1", creator_name="alice", is_anonymous=False,
            max_players=4, num_questions=5, theme=Theme.science,
        )
        assert r.num_questions == 5

    def test_create_room_num_questions_max_boundary(self):
        r = CreateRoomRequest(
            creator_id="uuid-1", creator_name="alice", is_anonymous=False,
            max_players=4, num_questions=20, theme=Theme.science,
        )
        assert r.num_questions == 20


class TestUserSchemas:
    def test_update_user_only_name(self):
        r = UpdateUserRequest(name="bob")
        assert r.name == "bob"
        assert r.password is None

    def test_update_user_only_password(self):
        r = UpdateUserRequest(password="newpass")
        assert r.password == "newpass"

    def test_update_user_both_none(self):
        r = UpdateUserRequest()
        assert r.name is None and r.password is None

    def test_user_stats_response(self):
        r = UserStatsResponse(
            games_played=10, avg_position=2.5,
            avg_points=47.3, highest_score=80, games_won=3,
        )
        assert r.games_played == 10


# ── Exceptions ────────────────────────────────────────────────────────────

class TestExceptions:
    @pytest.mark.parametrize("exc_class, expected_status, expected_code", [
        (InvalidArgumentError,    400, "INVALID_ARGUMENT"),
        (UnauthenticatedError,    401, "UNAUTHENTICATED"),
        (PermissionDeniedError,   403, "PERMISSION_DENIED"),
        (PlayerIdMismatchError,   403, "PLAYER_ID_MISMATCH"),
        (NotFoundError,           404, "NOT_FOUND"),
        (AlreadyExistsError,      409, "ALREADY_EXISTS"),
        (FailedPreconditionError, 409, "FAILED_PRECONDITION"),
        (UpstreamUnavailableError,503, "UNAVAILABLE"),
    ])
    def test_status_and_code(self, exc_class, expected_status, expected_code):
        exc = exc_class("test message")
        assert exc.status_code == expected_status
        assert exc.error_code == expected_code
        assert exc.message == "test message"

    def test_all_are_gateway_errors(self):
        for cls in [
            InvalidArgumentError, UnauthenticatedError, PermissionDeniedError,
            PlayerIdMismatchError, NotFoundError, AlreadyExistsError,
            FailedPreconditionError, UpstreamUnavailableError,
        ]:
            assert issubclass(cls, GatewayError)

    def test_player_id_mismatch_is_permission_denied(self):
        assert issubclass(PlayerIdMismatchError, PermissionDeniedError)


# ── Error Mapper ──────────────────────────────────────────────────────────

class FakeRpcError(grpc.RpcError):
    def __init__(self, code: grpc.StatusCode, details: str = "error"):
        self._code = code
        self._details = details

    def code(self):    return self._code
    def details(self): return self._details


class TestErrorMapper:
    @pytest.mark.parametrize("grpc_code, expected_exc", [
        (grpc.StatusCode.INVALID_ARGUMENT,    InvalidArgumentError),
        (grpc.StatusCode.UNAUTHENTICATED,     UnauthenticatedError),
        (grpc.StatusCode.PERMISSION_DENIED,   PermissionDeniedError),
        (grpc.StatusCode.NOT_FOUND,           NotFoundError),
        (grpc.StatusCode.ALREADY_EXISTS,      AlreadyExistsError),
        (grpc.StatusCode.FAILED_PRECONDITION, FailedPreconditionError),
        (grpc.StatusCode.UNAVAILABLE,         UpstreamUnavailableError),
    ])
    def test_grpc_code_maps_to_exception(self, grpc_code, expected_exc):
        exc = grpc_error_to_exception(FakeRpcError(grpc_code, "detail"))
        assert isinstance(exc, expected_exc)
        assert exc.message == "detail"

    def test_unknown_grpc_code_maps_to_unavailable(self):
        exc = grpc_error_to_exception(FakeRpcError(grpc.StatusCode.INTERNAL))
        assert isinstance(exc, UpstreamUnavailableError)
    def test_resource_exhausted_also_maps_to_unavailable(self):
        exc = grpc_error_to_exception(FakeRpcError(grpc.StatusCode.RESOURCE_EXHAUSTED))
        assert isinstance(exc, UpstreamUnavailableError)


# ── Middleware / Error Handler ────────────────────────────────────────────

@pytest.fixture(scope="module")
def test_client():
    """App FastAPI mínimo com os handlers registrados e um endpoint por erro."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/err/{code}")
    def raise_error(code: str):
        errors = {
            "invalid":     InvalidArgumentError("bad input"),
            "unauth":      UnauthenticatedError("not authenticated"),
            "forbidden":   PermissionDeniedError("forbidden"),
            "notfound":    NotFoundError("not found"),
            "exists":      AlreadyExistsError("already exists"),
            "precond":     FailedPreconditionError("wrong state"),
            "unavailable": UpstreamUnavailableError("upstream down"),
        }
        raise errors[code]

    return TestClient(app, raise_server_exceptions=False)


class TestErrorHandler:
    @pytest.mark.parametrize("path, expected_status, expected_error", [
        ("/err/invalid",     400, "INVALID_ARGUMENT"),
        ("/err/unauth",      401, "UNAUTHENTICATED"),
        ("/err/forbidden",   403, "PERMISSION_DENIED"),
        ("/err/notfound",    404, "NOT_FOUND"),
        ("/err/exists",      409, "ALREADY_EXISTS"),
        ("/err/precond",     409, "FAILED_PRECONDITION"),
        ("/err/unavailable", 503, "UNAVAILABLE"),
    ])
    def test_response_format(self, test_client, path, expected_status, expected_error):
        r = test_client.get(path)
        assert r.status_code == expected_status
        body = r.json()
        parsed = ErrorResponse(**body)
        assert parsed.status == expected_status
        assert parsed.error == expected_error

    def test_unhandled_exception_returns_500(self, test_client):
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/boom")
        def boom():
            raise RuntimeError("unexpected error")

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/boom")
        assert r.status_code == 500
        body = r.json()
        parsed = ErrorResponse(**body)
        assert parsed.status == 500
        assert parsed.error == "INTERNAL_SERVER_ERROR"
    
    def test_pydantic_validation_returns_400(self, test_client):
        """RequestValidationError (422 padrão) deve ser convertido para 400."""
        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/typed")
        def typed_endpoint(value: int):
            return {"value": value}

        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/typed?value=not_an_int")
        assert r.status_code == 400
        assert r.json()["error"] == "INVALID_ARGUMENT"
    