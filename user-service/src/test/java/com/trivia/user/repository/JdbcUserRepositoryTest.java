package com.trivia.user.repository;

import com.trivia.user.domain.User;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.any;

@ExtendWith(MockitoExtension.class)
class JdbcUserRepositoryTest {

    @Mock
    private JdbcTemplate primaryJdbcTemplate;

    @Mock
    private JdbcTemplate replicaJdbcTemplate;

    @Test
    @SuppressWarnings("unchecked")
    void findByNameFallsBackToPrimaryWhenReplicaDoesNotHaveUser() {
        UUID userId = UUID.randomUUID();
        User user = new User(userId, "alice", "hash");
        JdbcUserRepository repository = new JdbcUserRepository(primaryJdbcTemplate, replicaJdbcTemplate);

        when(replicaJdbcTemplate.query(anyString(), any(RowMapper.class), eq("alice")))
                .thenReturn(List.of());
        when(primaryJdbcTemplate.query(anyString(), any(RowMapper.class), eq("alice")))
                .thenReturn(List.of(user));

        Optional<User> result = repository.findByName("alice");

        assertThat(result).contains(user);
        verify(replicaJdbcTemplate).query(anyString(), any(RowMapper.class), eq("alice"));
        verify(primaryJdbcTemplate).query(anyString(), any(RowMapper.class), eq("alice"));
    }

    @Test
    @SuppressWarnings("unchecked")
    void findByNameDoesNotQueryPrimaryWhenReplicaFindsUser() {
        User user = new User(UUID.randomUUID(), "alice", "hash");
        JdbcUserRepository repository = new JdbcUserRepository(primaryJdbcTemplate, replicaJdbcTemplate);

        when(replicaJdbcTemplate.query(anyString(), any(RowMapper.class), eq("alice")))
                .thenReturn(List.of(user));

        Optional<User> result = repository.findByName("alice");

        assertThat(result).contains(user);
        verify(primaryJdbcTemplate, never()).query(anyString(), any(RowMapper.class), eq("alice"));
    }

    @Test
    void existsByNameUsesPrimaryDatabase() {
        JdbcUserRepository repository = new JdbcUserRepository(primaryJdbcTemplate, replicaJdbcTemplate);
        when(primaryJdbcTemplate.queryForObject(anyString(), eq(Boolean.class), eq("alice")))
                .thenReturn(true);

        boolean exists = repository.existsByName("alice");

        assertThat(exists).isTrue();
        verify(primaryJdbcTemplate).queryForObject(anyString(), eq(Boolean.class), eq("alice"));
        verify(replicaJdbcTemplate, never()).queryForObject(anyString(), eq(Boolean.class), eq("alice"));
    }
}
