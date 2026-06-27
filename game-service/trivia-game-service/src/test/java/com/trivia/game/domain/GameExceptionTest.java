package com.trivia.game.domain;

import io.grpc.Status;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class GameExceptionTest {
    @Test
    void unavailableMapsToGrpcUnavailable() {
        GameException exception = GameException.unavailable("shard down");

        assertEquals(Status.Code.UNAVAILABLE, exception.status().getCode());
        assertEquals("shard down", exception.status().getDescription());
    }
}
