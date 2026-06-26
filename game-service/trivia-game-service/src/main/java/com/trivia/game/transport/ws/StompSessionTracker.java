package com.trivia.game.transport.ws;

import com.trivia.game.application.GameCoordinator;
import org.springframework.context.event.EventListener;
import org.springframework.messaging.Message;
import org.springframework.messaging.simp.SimpMessageHeaderAccessor;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.socket.messaging.SessionDisconnectEvent;
import org.springframework.web.socket.messaging.SessionSubscribeEvent;

import java.security.Principal;
import java.util.concurrent.ConcurrentHashMap;

@Component
public class StompSessionTracker {
    private final GameCoordinator games;
    private final ConcurrentHashMap<String, PlayerSession> sessions = new ConcurrentHashMap<>();

    public StompSessionTracker(GameCoordinator games) {
        this.games = games;
    }

    public Message<?> handleInbound(Message<?> message) {
        StompHeaderAccessor accessor = StompHeaderAccessor.wrap(message);
        if (accessor.getCommand() == null) {
            return message;
        }
        if (accessor.getCommand() != StompCommand.CONNECT) {
            return message;
        }
        String playerId = accessor.getFirstNativeHeader("player-id");
        String roomCode = accessor.getFirstNativeHeader("room-code");
        if (playerId == null || playerId.isBlank() || roomCode == null || roomCode.isBlank()) {
            throw new IllegalArgumentException("Headers player-id e room-code são obrigatórios");
        }
        if (!games.canConnect(roomCode, playerId)) {
            throw new IllegalArgumentException("Jogador não pertence à sala informada");
        }
        accessor.setUser((Principal) () -> playerId);
        sessions.put(accessor.getSessionId(), new PlayerSession(playerId, roomCode));
        return MessageBuilder.createMessage(message.getPayload(), accessor.getMessageHeaders());
    }

    @EventListener
    public void onSubscribe(SessionSubscribeEvent event) {
        SimpMessageHeaderAccessor accessor = SimpMessageHeaderAccessor.wrap(event.getMessage());
        PlayerSession session = sessions.get(accessor.getSessionId());
        if (session == null) {
            return;
        }
        String destination = accessor.getDestination();
        if (("/user/queue/rooms/" + session.roomCode()).equals(destination)) {
            games.playerConnected(session.roomCode(), session.playerId());
        }
    }

    @EventListener
    public void onDisconnect(SessionDisconnectEvent event) {
        sessions.remove(event.getSessionId());
    }
}
