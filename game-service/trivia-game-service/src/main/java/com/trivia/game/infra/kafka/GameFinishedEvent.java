package com.trivia.game.infra.kafka;

import java.time.Instant;
import java.util.List;

public record GameFinishedEvent(String room_id, Instant finished_at, String theme, List<Result> results) {
    public record Result(
            String player_id,
            String player_name,
            boolean is_anonymous,
            int score,
            int position,
            boolean won
    ) {
    }
}

