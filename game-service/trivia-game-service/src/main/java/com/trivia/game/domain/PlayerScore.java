package com.trivia.game.domain;

public record PlayerScore(String playerId, String playerName, boolean anonymous, int score) {
}

