package com.trivia.game.domain;

import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.LinkedHashMap;

import static org.junit.jupiter.api.Assertions.assertEquals;

class CreditDistributorTest {
    @Test
    void givesTheRemainderToTheFastestCorrectAnswer() {
        var answers = new LinkedHashMap<String, Instant>();
        answers.put("player-1", Instant.parse("2026-06-20T12:00:01Z"));
        answers.put("player-2", Instant.parse("2026-06-20T12:00:02Z"));
        answers.put("player-3", Instant.parse("2026-06-20T12:00:03Z"));

        var credits = CreditDistributor.distribute(answers);

        assertEquals(3, credits.size());
        assertEquals(new RoundCredit("player-1", 6, 1), credits.get(0));
        assertEquals(new RoundCredit("player-2", 3, 2), credits.get(1));
        assertEquals(new RoundCredit("player-3", 1, 3), credits.get(2));
        assertEquals(10, credits.stream().mapToInt(RoundCredit::earned).sum());
    }

    @Test
    void breaksEqualTimestampsByPlayerId() {
        Instant timestamp = Instant.parse("2026-06-20T12:00:01Z");
        var answers = new LinkedHashMap<String, Instant>();
        answers.put("player-z", timestamp);
        answers.put("player-a", timestamp);

        var credits = CreditDistributor.distribute(answers);

        assertEquals("player-a", credits.get(0).playerId());
        assertEquals(7, credits.get(0).earned());
        assertEquals(3, credits.get(1).earned());
    }

    @Test
    void givesNoCreditsWhenNobodyAnswersCorrectly() {
        assertEquals(0, CreditDistributor.distribute(java.util.Map.of()).size());
    }
}

