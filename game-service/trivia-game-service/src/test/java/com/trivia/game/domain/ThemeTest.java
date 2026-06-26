package com.trivia.game.domain;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ThemeTest {
    @Test
    void routesThemesToTheContractedShards() {
        assertEquals(Theme.Shard.A, Theme.from("science").shard());
        assertEquals(Theme.Shard.A, Theme.from("society_and_culture").shard());
        assertEquals(Theme.Shard.B, Theme.from("music").shard());
        assertEquals(Theme.Shard.B, Theme.from("general_knowledge").shard());
    }

    @Test
    void rejectsUnknownThemes() {
        assertThrows(GameException.class, () -> Theme.from("unknown"));
    }
}

