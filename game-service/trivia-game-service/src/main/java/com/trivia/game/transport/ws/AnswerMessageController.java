package com.trivia.game.transport.ws;

import com.trivia.game.application.AnswerCommand;
import com.trivia.game.application.GameCoordinator;
import org.springframework.messaging.handler.annotation.DestinationVariable;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.stereotype.Controller;

import java.security.Principal;

@Controller
public class AnswerMessageController {
    private final GameCoordinator games;

    public AnswerMessageController(GameCoordinator games) {
        this.games = games;
    }

    @MessageMapping("/rooms/{roomCode}/answer")
    public void answer(@DestinationVariable String roomCode, AnswerCommand answer, Principal principal) {
        if (principal != null) {
            games.submitAnswer(roomCode, principal.getName(), answer);
        }
    }
}

