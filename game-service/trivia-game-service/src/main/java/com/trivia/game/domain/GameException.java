package com.trivia.game.domain;

import io.grpc.Status;

public class GameException extends RuntimeException {
    private final Status status;

    private GameException(Status status, String message) {
        super(message);
        this.status = status.withDescription(message);
    }

    public Status status() {
        return status;
    }

    public static GameException invalidArgument(String message) {
        return new GameException(Status.INVALID_ARGUMENT, message);
    }

    public static GameException notFound(String message) {
        return new GameException(Status.NOT_FOUND, message);
    }

    public static GameException forbidden(String message) {
        return new GameException(Status.PERMISSION_DENIED, message);
    }

    public static GameException precondition(String message) {
        return new GameException(Status.FAILED_PRECONDITION, message);
    }

    public static GameException unavailable(String message) {
        return new GameException(Status.UNAVAILABLE, message);
    }
}

