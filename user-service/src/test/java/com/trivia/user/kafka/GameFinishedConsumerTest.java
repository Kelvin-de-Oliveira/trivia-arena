package com.trivia.user.kafka;

import com.trivia.user.repository.UserStatsRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.kafka.support.Acknowledgment;

import java.util.List;
import java.util.UUID;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GameFinishedConsumerTest {

    @Mock
    private UserStatsRepository userStatsRepository;

    @Mock
    private Acknowledgment acknowledgment;

    @Test
    void updatesRegisteredPlayersIgnoresAnonymousPlayersAndMarksGameProcessed() {
        UUID registeredUserId = UUID.randomUUID();
        GameFinishedConsumer consumer = new GameFinishedConsumer(userStatsRepository);
        GameFinishedEvent event = new GameFinishedEvent(
                "ROOM1",
                "2026-06-29T01:30:00Z",
                "science",
                List.of(
                        new GameFinishedEvent.PlayerResult(
                                registeredUserId.toString(),
                                "alice",
                                false,
                                24,
                                1,
                                true
                        ),
                        new GameFinishedEvent.PlayerResult(
                                "anon:abc",
                                "visitor",
                                true,
                                16,
                                2,
                                false
                        )
                )
        );
        when(userStatsRepository.isGameProcessed("ROOM1")).thenReturn(false);

        consumer.onGameFinished(event, acknowledgment);

        verify(userStatsRepository).applyGameResult(registeredUserId, 1, 24, true);
        verify(userStatsRepository).markGameProcessed("ROOM1");
        verify(acknowledgment).acknowledge();
    }

    @Test
    void skipsAlreadyProcessedGameAndAcknowledgesMessage() {
        GameFinishedConsumer consumer = new GameFinishedConsumer(userStatsRepository);
        GameFinishedEvent event = new GameFinishedEvent(
                "ROOM1",
                "2026-06-29T01:30:00Z",
                "science",
                List.of(
                        new GameFinishedEvent.PlayerResult(
                                UUID.randomUUID().toString(),
                                "alice",
                                false,
                                24,
                                1,
                                true
                        )
                )
        );
        when(userStatsRepository.isGameProcessed("ROOM1")).thenReturn(true);

        consumer.onGameFinished(event, acknowledgment);

        verify(userStatsRepository, never()).applyGameResult(
                org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.anyInt(),
                org.mockito.ArgumentMatchers.anyInt(),
                org.mockito.ArgumentMatchers.anyBoolean()
        );
        verify(userStatsRepository, never()).markGameProcessed("ROOM1");
        verify(acknowledgment).acknowledge();
    }
}
