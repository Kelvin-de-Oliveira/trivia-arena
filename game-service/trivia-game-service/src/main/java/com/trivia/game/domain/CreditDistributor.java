package com.trivia.game.domain;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public final class CreditDistributor {
    private static final int ROUND_POOL = 10;

    private CreditDistributor() {
    }

    public static List<RoundCredit> distribute(Map<String, java.time.Instant> correctAnswers) {
        var ordered = correctAnswers.entrySet().stream()
                .sorted(java.util.Comparator.<Map.Entry<String, java.time.Instant>, java.time.Instant>comparing(Map.Entry::getValue)
                        .thenComparing(Map.Entry::getKey))
                .toList();
        int count = ordered.size();
        if (count == 0) {
            return List.of();
        }

        int totalWeight = count * (count + 1) / 2;
        int distributed = 0;
        var credits = new ArrayList<RoundCredit>(count);
        for (int index = 0; index < count; index++) {
            int weight = count - index;
            int earned = (weight * ROUND_POOL) / totalWeight;
            distributed += earned;
            credits.add(new RoundCredit(ordered.get(index).getKey(), earned, index + 1));
        }
        int remainder = ROUND_POOL - distributed;
        var winner = credits.get(0);
        credits.set(0, new RoundCredit(winner.playerId(), winner.earned() + remainder, winner.position()));
        return List.copyOf(credits);
    }
}
