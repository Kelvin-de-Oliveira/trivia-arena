package com.trivia.game.domain;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record RoomSnapshot(
        String roomCode,
        RoomStatus status,
        String creatorId,
        int maxPlayers,
        int numQuestions,
        Theme theme,
        int currentQuestionIdx,
        List<UUID> questionIds,
        UUID runId,
        Instant roundDeadline,
        List<PlayerScore> players
) {
    public boolean isParticipant(String playerId) {
        return players.stream().anyMatch(player -> player.playerId().equals(playerId));
    }
}

