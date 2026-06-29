package com.trivia.game.application;

import com.trivia.game.config.GameProperties;
import com.trivia.game.domain.PlayerScore;
import com.trivia.game.domain.Question;
import com.trivia.game.domain.RoomSnapshot;
import com.trivia.game.domain.RoomStatus;
import com.trivia.game.domain.Theme;
import com.trivia.game.infra.events.RoomEventBus;
import com.trivia.game.infra.kafka.GameFinishedPublisher;
import com.trivia.game.infra.questions.QuestionRepository;
import com.trivia.game.infra.redis.RoomRedisRepository;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.scheduling.TaskScheduler;

import java.time.Clock;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.Date;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ScheduledFuture;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyList;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class GameCoordinatorTest {

    @Mock
    private RoomRedisRepository rooms;

    @Mock
    private QuestionRepository questions;

    @Mock
    private RoomEventBus events;

    @Mock
    private GameFinishedPublisher finishedPublisher;

    @Mock
    private TaskScheduler scheduler;

    @Test
    @SuppressWarnings({"unchecked", "rawtypes"})
    void finishesRoundBeforeDeadlineWhenEveryPlayerAnswered() {
        String roomCode = "ROOM01";
        UUID runId = UUID.randomUUID();
        UUID questionId = UUID.randomUUID();
        Instant now = Instant.parse("2026-06-20T12:00:00Z");
        Question question = new Question(questionId, "Question?", "A", "B", "C", "D", "a");
        List<PlayerScore> players = List.of(
                new PlayerScore("player-1", "Ana", false, 0),
                new PlayerScore("player-2", "Bia", false, 0)
        );
        RoomSnapshot inProgress = new RoomSnapshot(
                roomCode,
                RoomStatus.IN_PROGRESS,
                "player-1",
                2,
                1,
                Theme.SCIENCE,
                0,
                List.of(questionId),
                runId,
                now.plusSeconds(20),
                players
        );
        RoomSnapshot finished = new RoomSnapshot(
                roomCode,
                RoomStatus.FINISHED,
                "player-1",
                2,
                1,
                Theme.SCIENCE,
                0,
                List.of(questionId),
                runId,
                null,
                List.of(
                        new PlayerScore("player-1", "Ana", false, 7),
                        new PlayerScore("player-2", "Bia", false, 3)
                )
        );
        ScheduledFuture future = mock(ScheduledFuture.class);
        when(scheduler.scheduleAtFixedRate(any(Runnable.class), anyLong())).thenReturn(future);
        when(scheduler.schedule(any(Runnable.class), any(Date.class))).thenReturn(future);
        when(rooms.findRoom(roomCode)).thenReturn(java.util.Optional.of(inProgress));
        when(rooms.questions(roomCode)).thenReturn(Map.of(questionId, question));
        when(rooms.recordAnswerAttempt(roomCode, 0, "player-2", now, 60L)).thenReturn(true);
        when(rooms.answerAttemptCount(roomCode, 0)).thenReturn(2L);
        when(rooms.claimLeader(eq(roomCode), any(String.class), any())).thenReturn(true);
        when(rooms.ownsLeader(eq(roomCode), any(String.class))).thenReturn(true);
        when(rooms.beginFinalization(eq(roomCode), eq(0), eq(runId), any())).thenReturn(true);
        when(rooms.answers(roomCode, 0)).thenReturn(Map.of(
                "player-1", now.minusSeconds(1),
                "player-2", now
        ));
        when(rooms.applyRound(eq(roomCode), eq(inProgress), anyList(), any(Instant.class), eq(60L))).thenReturn(finished);
        GameCoordinator coordinator = new GameCoordinator(
                rooms,
                questions,
                events,
                finishedPublisher,
                new GameProperties(20_000, 60, 10_000, 1_000),
                scheduler,
                Clock.fixed(now, ZoneOffset.UTC)
        );

        coordinator.submitAnswer(roomCode, "player-2", new AnswerCommand("answer", questionId, "a"));

        verify(rooms).recordAnswerAttempt(roomCode, 0, "player-2", now, 60L);
        verify(rooms).recordCorrectAnswer(roomCode, 0, "player-2", now, 60L);
        verify(rooms).applyRound(eq(roomCode), eq(inProgress), anyList(), any(Instant.class), eq(60L));
        ArgumentCaptor<Map<String, Object>> eventCaptor = ArgumentCaptor.forClass(Map.class);
        verify(events, atLeastOnce()).broadcast(eq(roomCode), eventCaptor.capture());
        assertEquals("round_result", eventCaptor.getAllValues().get(0).get("type"));
        assertEquals("game_over", eventCaptor.getAllValues().get(1).get("type"));
    }
}
