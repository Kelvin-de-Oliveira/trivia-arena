package com.trivia.game.infra.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class GameFinishedPublisher {
    private static final Logger log = LoggerFactory.getLogger(GameFinishedPublisher.class);
    private static final String TOPIC = "game-finished";

    private final KafkaTemplate<String, GameFinishedEvent> kafka;

    public GameFinishedPublisher(KafkaTemplate<String, GameFinishedEvent> kafka) {
        this.kafka = kafka;
    }

    public void publish(String roomCode, GameFinishedEvent event) {
        kafka.send(TOPIC, roomCode, event).whenComplete((result, error) -> {
            if (error != null) {
                log.error("Could not publish game-finished for room {}", roomCode, error);
            }
        });
    }
}

