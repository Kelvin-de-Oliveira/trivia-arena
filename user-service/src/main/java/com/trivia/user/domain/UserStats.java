package com.trivia.user.domain;

import java.util.UUID;

public record UserStats(
        UUID userId,
        int gamesPlayed,
        int gamesWon,
        double avgPosition,
        double avgPoints,
        int highestScore
) {
}