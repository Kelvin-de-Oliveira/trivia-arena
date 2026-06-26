package com.trivia.game.domain;

public record RankedPlayer(String playerId, String playerName, boolean anonymous, int totalScore, int position) {
}

