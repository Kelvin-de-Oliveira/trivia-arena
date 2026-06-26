package com.trivia.game.transport.grpc;

import com.trivia.game.application.GameCoordinator;
import com.trivia.game.domain.GameException;
import com.trivia.game.domain.PlayerScore;
import com.trivia.game.domain.RoomSnapshot;
import com.trivia.game.grpc.GameServiceGrpc;
import com.trivia.game.grpc.GameServiceProto.CreateRoomRequest;
import com.trivia.game.grpc.GameServiceProto.CreateRoomResponse;
import com.trivia.game.grpc.GameServiceProto.GetRoomRequest;
import com.trivia.game.grpc.GameServiceProto.GetRoomResponse;
import com.trivia.game.grpc.GameServiceProto.JoinRoomRequest;
import com.trivia.game.grpc.GameServiceProto.JoinRoomResponse;
import com.trivia.game.grpc.GameServiceProto.Player;
import com.trivia.game.grpc.GameServiceProto.RestartGameRequest;
import com.trivia.game.grpc.GameServiceProto.StartGameRequest;
import com.trivia.game.grpc.GameServiceProto.StartGameResponse;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import net.devh.boot.grpc.server.service.GrpcService;

import java.util.function.Supplier;

@GrpcService
public class GameGrpcService extends GameServiceGrpc.GameServiceImplBase {
    private final GameCoordinator games;

    public GameGrpcService(GameCoordinator games) {
        this.games = games;
    }

    @Override
    public void createRoom(CreateRoomRequest request, StreamObserver<CreateRoomResponse> observer) {
        respond(observer, () -> CreateRoomResponse.newBuilder()
                .setRoomCode(games.createRoom(
                        request.getCreatorId(), request.getCreatorName(), request.getIsAnonymous(),
                        request.getMaxPlayers(), request.getNumQuestions(), request.getTheme()))
                .build());
    }

    @Override
    public void joinRoom(JoinRoomRequest request, StreamObserver<JoinRoomResponse> observer) {
        respond(observer, () -> {
            RoomSnapshot room = games.joinRoom(request.getRoomCode(), request.getPlayerId(), request.getPlayerName(), request.getIsAnonymous());
            return JoinRoomResponse.newBuilder()
                    .addAllPlayers(room.players().stream().map(this::player).toList())
                    .setStatus(status(room))
                    .setTheme(room.theme().value())
                    .setMaxPlayers(room.maxPlayers())
                    .build();
        });
    }

    @Override
    public void startGame(StartGameRequest request, StreamObserver<StartGameResponse> observer) {
        respond(observer, () -> StartGameResponse.newBuilder()
                .setStarted(games.startGame(request.getRoomCode(), request.getRequesterId()))
                .build());
    }

    @Override
    public void restartGame(RestartGameRequest request, StreamObserver<StartGameResponse> observer) {
        respond(observer, () -> StartGameResponse.newBuilder()
                .setStarted(games.restartGame(request.getRoomCode(), request.getRequesterId(), request.getNewTheme()))
                .build());
    }

    @Override
    public void getRoom(GetRoomRequest request, StreamObserver<GetRoomResponse> observer) {
        respond(observer, () -> {
            RoomSnapshot room = games.getRoom(request.getRoomCode());
            return GetRoomResponse.newBuilder()
                    .setRoomCode(room.roomCode())
                    .setStatus(status(room))
                    .setTheme(room.theme().value())
                    .setMaxPlayers(room.maxPlayers())
                    .setNumQuestions(room.numQuestions())
                    .addAllPlayers(room.players().stream().map(this::player).toList())
                    .build();
        });
    }

    private Player player(PlayerScore player) {
        return Player.newBuilder()
                .setPlayerId(player.playerId())
                .setPlayerName(player.playerName())
                .setIsAnonymous(player.anonymous())
                .setScore(player.score())
                .build();
    }

    private com.trivia.game.grpc.GameServiceProto.RoomStatus status(RoomSnapshot room) {
        return com.trivia.game.grpc.GameServiceProto.RoomStatus.valueOf(room.status().name());
    }

    private <T> void respond(StreamObserver<T> observer, Supplier<T> operation) {
        try {
            observer.onNext(operation.get());
            observer.onCompleted();
        } catch (GameException exception) {
            observer.onError(exception.status().asRuntimeException());
        } catch (Exception exception) {
            observer.onError(Status.INTERNAL.withDescription("Erro interno no Game Service").withCause(exception).asRuntimeException());
        }
    }
}

