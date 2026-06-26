package com.trivia.game.infra.redis;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.trivia.game.domain.PlayerMeta;
import com.trivia.game.domain.Theme;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.time.Instant;
import java.util.ArrayList;
import java.util.concurrent.Executors;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

@Testcontainers(disabledWithoutDocker = true)
class RoomRedisRepositoryIntegrationTest {
    @Container
    static final GenericContainer<?> REDIS = new GenericContainer<>(DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(6379);

    private static LettuceConnectionFactory connectionFactory;
    private static RoomRedisRepository rooms;

    @BeforeAll
    static void setUp() {
        connectionFactory = new LettuceConnectionFactory(REDIS.getHost(), REDIS.getMappedPort(6379));
        connectionFactory.afterPropertiesSet();
        var template = new StringRedisTemplate(connectionFactory);
        template.afterPropertiesSet();
        rooms = new RoomRedisRepository(template, new ObjectMapper());
    }

    @AfterAll
    static void tearDown() {
        connectionFactory.destroy();
    }

    @Test
    void admitsOnlyOneConcurrentPlayerWhenOneSlotRemains() throws Exception {
        String room = "ROOM01";
        assertTrue(rooms.createRoom(room, new PlayerMeta("creator", "Ana", false), 2, 5, Theme.SCIENCE, 60));
        try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
            var futures = new ArrayList<java.util.concurrent.Future<RoomRedisRepository.JoinResult>>();
            for (int index = 0; index < 8; index++) {
                int player = index;
                futures.add(executor.submit(() -> rooms.joinRoom(room,
                        new PlayerMeta("player-" + player, "P" + player, false), 60)));
            }
            int admitted = 0;
            for (var future : futures) {
                if (future.get() == RoomRedisRepository.JoinResult.JOINED) {
                    admitted++;
                }
            }
            assertEquals(1, admitted);
            assertEquals(2, rooms.getRoom(room).players().size());
        }
    }

    @Test
    void keepsOnlyTheFirstCorrectAnswerForAPlayer() {
        String room = "ROOM02";
        assertTrue(rooms.createRoom(room, new PlayerMeta("creator", "Ana", false), 2, 5, Theme.SCIENCE, 60));
        Instant first = Instant.parse("2026-06-20T12:00:01Z");
        Instant second = Instant.parse("2026-06-20T12:00:02Z");

        assertTrue(rooms.recordCorrectAnswer(room, 0, "creator", first, 60));
        assertFalse(rooms.recordCorrectAnswer(room, 0, "creator", second, 60));
        assertEquals(first, rooms.answers(room, 0).get("creator"));
    }
}

