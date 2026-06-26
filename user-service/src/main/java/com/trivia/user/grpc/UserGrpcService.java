package com.trivia.user.grpc;

import com.trivia.user.domain.User;
import com.trivia.user.domain.UserStats;
import com.trivia.user.exception.AlreadyExistsException;
import com.trivia.user.exception.InvalidArgumentException;
import com.trivia.user.exception.UnauthenticatedException;
import com.trivia.user.repository.UserRepository;
import com.trivia.user.repository.UserStatsRepository;
import com.trivia.user.security.PasswordHasher;
import io.grpc.Status;
import io.grpc.stub.StreamObserver;
import org.lognet.springboot.grpc.GRpcService;

import java.util.Optional;
import java.util.UUID;

@GRpcService
public class UserGrpcService extends UserServiceGrpc.UserServiceImplBase {

    private final UserRepository userRepository;
    private final UserStatsRepository userStatsRepository;
    private final PasswordHasher passwordHasher;

    public UserGrpcService(UserRepository userRepository,
                           UserStatsRepository userStatsRepository,
                           PasswordHasher passwordHasher) {
        this.userRepository = userRepository;
        this.userStatsRepository = userStatsRepository;
        this.passwordHasher = passwordHasher;
    }

    @Override
    public void registerUser(UserServiceProto.RegisterUserRequest request,
                             StreamObserver<UserServiceProto.AuthResponse> responseObserver) {
        try {
            String name = request.getName();
            String password = request.getPassword();

            if (name.isBlank() || password.isBlank()) {
                throw new InvalidArgumentException("name and password must not be empty");
            }

            if (userRepository.existsByName(name)) {
                throw new AlreadyExistsException("name already registered: " + name);
            }

            String hash = passwordHasher.hash(password);
            UUID userId = userRepository.insert(name, hash);
            userStatsRepository.insertEmptyStats(userId);

            UserServiceProto.AuthResponse response = UserServiceProto.AuthResponse.newBuilder()
                    .setUserId(userId.toString())
                    .setName(name)
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();

        } catch (InvalidArgumentException e) {
            responseObserver.onError(Status.INVALID_ARGUMENT.withDescription(e.getMessage()).asRuntimeException());
        } catch (AlreadyExistsException e) {
            responseObserver.onError(Status.ALREADY_EXISTS.withDescription(e.getMessage()).asRuntimeException());
        }
    }

    @Override
    public void loginUser(UserServiceProto.LoginUserRequest request,
                          StreamObserver<UserServiceProto.AuthResponse> responseObserver) {
        try {
            String name = request.getName();
            String password = request.getPassword();

            User user = userRepository.findByName(name)
                    .orElseThrow(() -> new UnauthenticatedException("invalid credentials"));

            if (!passwordHasher.matches(password, user.passwordHash())) {
                throw new UnauthenticatedException("invalid credentials");
            }

            UserServiceProto.AuthResponse response = UserServiceProto.AuthResponse.newBuilder()
                    .setUserId(user.id().toString())
                    .setName(user.name())
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();

        } catch (UnauthenticatedException e) {
            responseObserver.onError(Status.UNAUTHENTICATED.withDescription(e.getMessage()).asRuntimeException());
        }
    }

    @Override
    public void updateUser(UserServiceProto.UpdateUserRequest request,
                           StreamObserver<UserServiceProto.UpdateUserResponse> responseObserver) {
        try {
            boolean hasName = request.hasName();
            boolean hasPassword = request.hasPassword();

            if (!hasName && !hasPassword) {
                throw new InvalidArgumentException("at least one of name or password must be sent");
            }

            UUID userId = UUID.fromString(request.getUserId());

            if (hasName) {
                String newName = request.getName();
                if (userRepository.existsByName(newName)) {
                    throw new AlreadyExistsException("name already in use: " + newName);
                }
                userRepository.updateName(userId, newName);
            }

            if (hasPassword) {
                String newHash = passwordHasher.hash(request.getPassword());
                userRepository.updatePasswordHash(userId, newHash);
            }

            UserServiceProto.UpdateUserResponse response = UserServiceProto.UpdateUserResponse.newBuilder()
                    .setSuccess(true)
                    .build();

            responseObserver.onNext(response);
            responseObserver.onCompleted();

        } catch (InvalidArgumentException e) {
            responseObserver.onError(Status.INVALID_ARGUMENT.withDescription(e.getMessage()).asRuntimeException());
        } catch (AlreadyExistsException e) {
            responseObserver.onError(Status.ALREADY_EXISTS.withDescription(e.getMessage()).asRuntimeException());
        }
    }

    @Override
    public void getUserStats(UserServiceProto.GetUserStatsRequest request,
                             StreamObserver<UserServiceProto.GetUserStatsResponse> responseObserver) {
        UUID userId = UUID.fromString(request.getUserId());

        Optional<UserStats> statsOpt = userStatsRepository.findByUserId(userId);

        UserServiceProto.GetUserStatsResponse response = statsOpt
                .map(stats -> UserServiceProto.GetUserStatsResponse.newBuilder()
                        .setGamesPlayed(stats.gamesPlayed())
                        .setAvgPosition(stats.avgPosition())
                        .setAvgPoints(stats.avgPoints())
                        .setHighestScore(stats.highestScore())
                        .setGamesWon(stats.gamesWon())
                        .build())
                .orElseGet(() -> UserServiceProto.GetUserStatsResponse.newBuilder()
                        .setGamesPlayed(0)
                        .setAvgPosition(0)
                        .setAvgPoints(0)
                        .setHighestScore(0)
                        .setGamesWon(0)
                        .build());

        responseObserver.onNext(response);
        responseObserver.onCompleted();
    }
}