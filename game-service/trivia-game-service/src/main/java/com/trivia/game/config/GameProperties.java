package com.trivia.game.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "game")
public record GameProperties(
        long questionTimeoutMs,
        long roomTtlSeconds,
        long leaderLeaseMs,
        long recoveryScanMs
) {
    public GameProperties {
        if (questionTimeoutMs <= 0 || roomTtlSeconds <= 0 || leaderLeaseMs <= 0 || recoveryScanMs <= 0) {
            throw new IllegalArgumentException("Game timing properties must be positive");
        }
    }
}

