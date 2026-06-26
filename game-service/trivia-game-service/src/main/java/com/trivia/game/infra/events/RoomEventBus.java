package com.trivia.game.infra.events;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trivia.game.infra.redis.RoomRedisRepository;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.data.redis.listener.PatternTopic;
import org.springframework.data.redis.listener.RedisMessageListenerContainer;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.util.Map;

@Component
public class RoomEventBus implements MessageListener {
    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;
    private final SimpMessagingTemplate messaging;

    public RoomEventBus(
            StringRedisTemplate redis,
            ObjectMapper objectMapper,
            SimpMessagingTemplate messaging,
            RedisMessageListenerContainer listenerContainer
    ) {
        this.redis = redis;
        this.objectMapper = objectMapper;
        this.messaging = messaging;
        listenerContainer.addMessageListener(this, new PatternTopic("room:*:broadcast"));
    }

    public void broadcast(String roomCode, Map<String, Object> event) {
        redis.convertAndSend(RoomRedisRepository.broadcastChannel(roomCode), write(event));
    }

    public void sendPrivate(String playerId, String roomCode, Map<String, Object> event) {
        messaging.convertAndSendToUser(playerId, "/queue/rooms/" + roomCode, event);
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        String channel = new String(message.getChannel(), StandardCharsets.UTF_8);
        String payload = new String(message.getBody(), StandardCharsets.UTF_8);
        String roomCode = channel.substring("room:".length(), channel.length() - ":broadcast".length());
        messaging.convertAndSend("/topic/rooms/" + roomCode, read(payload));
    }

    private String write(Map<String, Object> event) {
        try {
            return objectMapper.writeValueAsString(event);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Não foi possível serializar evento de sala", exception);
        }
    }

    private Map<String, Object> read(String payload) {
        try {
            return objectMapper.readValue(payload, new TypeReference<>() { });
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Evento Redis inválido", exception);
        }
    }
}

