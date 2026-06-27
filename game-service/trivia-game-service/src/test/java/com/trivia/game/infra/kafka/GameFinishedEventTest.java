package com.trivia.game.infra.kafka;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.json.JsonMapper;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

class GameFinishedEventTest {
    @Test
    void serializesTheContractedKafkaFields() throws Exception {
        var event = new GameFinishedEvent(
                "ABC123",
                Instant.parse("2026-06-18T14:32:00Z"),
                "science",
                5,
                List.of(new GameFinishedEvent.Result("player-1", "Ana", false, 47, 1, true))
        );

        var mapper = JsonMapper.builder().findAndAddModules().build();
        JsonNode json = mapper.readTree(mapper.writeValueAsString(event));

        assertEquals("ABC123", json.get("room_code").asText());
        assertFalse(json.has("room_id"));
        assertEquals("science", json.get("theme").asText());
        assertEquals(5, json.get("num_questions").asInt());
        assertEquals("player-1", json.get("results").get(0).get("player_id").asText());
        assertTrue(json.get("results").get(0).get("won").asBoolean());
    }
}
