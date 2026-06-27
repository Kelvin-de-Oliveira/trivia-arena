package com.trivia.game.infra.kafka;

import java.time.Instant;
import java.util.List;

public record GameFinishedEvent(
        String room_code,
        Instant finished_at,
        String theme,
        int num_questions,
        List<Result> results
) {
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

