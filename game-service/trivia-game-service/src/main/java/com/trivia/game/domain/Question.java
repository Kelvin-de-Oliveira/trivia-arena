package com.trivia.game.domain;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

public record Question(
        UUID id,
        String text,
        String optionA,
        String optionB,
        String optionC,
        String optionD,
        String correctOption
) {
    public Map<String, String> options() {
        var options = new LinkedHashMap<String, String>();
        options.put("a", optionA);
        options.put("b", optionB);
        options.put("c", optionC);
        options.put("d", optionD);
        return options;
    }

    public boolean isValidOption(String option) {
        return option != null && options().containsKey(option.toLowerCase());
    }

    public boolean isCorrect(String option) {
        return correctOption.equalsIgnoreCase(option);
    }
}

