package com.trivia.user.repository;

import com.trivia.user.domain.UserStats;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class JdbcUserStatsRepositoryTest {

    @Mock
    private JdbcTemplate primaryJdbcTemplate;

    @Mock
    private JdbcTemplate replicaJdbcTemplate;

    @Test
    @SuppressWarnings("unchecked")
    void findByUserIdReadsFromPrimaryDatabase() {
        UUID userId = UUID.randomUUID();
        UserStats stats = new UserStats(userId, 1, 1, 1.0, 24.0, 24);
        JdbcUserStatsRepository repository = new JdbcUserStatsRepository(primaryJdbcTemplate, replicaJdbcTemplate);

        when(primaryJdbcTemplate.query(anyString(), any(RowMapper.class), eq(userId)))
                .thenReturn(List.of(stats));

        Optional<UserStats> result = repository.findByUserId(userId);

        assertThat(result).contains(stats);
        verify(primaryJdbcTemplate).query(anyString(), any(RowMapper.class), eq(userId));
        verify(replicaJdbcTemplate, never()).query(anyString(), any(RowMapper.class), eq(userId));
    }

    @Test
    void processedGameLookupUsesRoomIdColumn() {
        JdbcUserStatsRepository repository = new JdbcUserStatsRepository(primaryJdbcTemplate, replicaJdbcTemplate);
        when(primaryJdbcTemplate.queryForObject(contains("processed_games WHERE room_id"), eq(Boolean.class), eq("ROOM1")))
                .thenReturn(false);

        boolean processed = repository.isGameProcessed("ROOM1");

        assertThat(processed).isFalse();
        verify(primaryJdbcTemplate).queryForObject(contains("processed_games WHERE room_id"), eq(Boolean.class), eq("ROOM1"));
    }

    @Test
    void markGameProcessedUsesRoomIdColumn() {
        JdbcUserStatsRepository repository = new JdbcUserStatsRepository(primaryJdbcTemplate, replicaJdbcTemplate);

        repository.markGameProcessed("ROOM1");

        verify(primaryJdbcTemplate).update(contains("INSERT INTO processed_games (room_id)"), eq("ROOM1"));
    }
}
