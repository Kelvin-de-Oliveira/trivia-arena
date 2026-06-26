package com.trivia.game.application;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.UUID;

public record AnswerCommand(String type, @JsonProperty("question_id") UUID questionId, String option) {
}
