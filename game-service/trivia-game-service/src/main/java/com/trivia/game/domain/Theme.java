package com.trivia.game.domain;

import java.util.Arrays;

public enum Theme {
    MUSIC(Shard.B),
    SPORT_AND_LEISURE(Shard.B),
    FILM_AND_TV(Shard.B),
    ARTS_AND_LITERATURE(Shard.A),
    HISTORY(Shard.A),
    SOCIETY_AND_CULTURE(Shard.A),
    SCIENCE(Shard.A),
    GEOGRAPHY(Shard.A),
    FOOD_AND_DRINK(Shard.B),
    GENERAL_KNOWLEDGE(Shard.B);

    public enum Shard { A, B }

    private final Shard shard;

    Theme(Shard shard) {
        this.shard = shard;
    }

    public Shard shard() {
        return shard;
    }

    public String value() {
        return name().toLowerCase();
    }

    public static Theme from(String value) {
        return Arrays.stream(values())
                .filter(theme -> theme.value().equals(value))
                .findFirst()
                .orElseThrow(() -> GameException.invalidArgument("theme inválido"));
    }
}

