package com.trivia.user.repository;

import com.trivia.user.domain.UserStats;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcUserStatsRepository implements UserStatsRepository {

    private static final RowMapper<UserStats> STATS_ROW_MAPPER = (rs, rowNum) -> new UserStats(
            UUID.fromString(rs.getString("user_id")),
            rs.getInt("games_played"),
            rs.getInt("games_won"),
            rs.getDouble("avg_position"),
            rs.getDouble("avg_points"),
            rs.getInt("highest_score")
    );

    private final JdbcTemplate primaryJdbcTemplate;
    private final JdbcTemplate replicaJdbcTemplate;

    public JdbcUserStatsRepository(@Qualifier("primaryJdbcTemplate") JdbcTemplate primaryJdbcTemplate,
                                   @Qualifier("replicaJdbcTemplate") JdbcTemplate replicaJdbcTemplate) {
        this.primaryJdbcTemplate = primaryJdbcTemplate;
        this.replicaJdbcTemplate = replicaJdbcTemplate;
    }

    @Override
    public Optional<UserStats> findByUserId(UUID userId) {
        String sql = "SELECT user_id, games_played, games_won, avg_position, avg_points, highest_score " +
                "FROM user_stats WHERE user_id = ?";
        return primaryJdbcTemplate.query(sql, STATS_ROW_MAPPER, userId)
                .stream()
                .findFirst();
    }

    @Override
    public void insertEmptyStats(UUID userId) {
        String sql = "INSERT INTO user_stats (user_id) VALUES (?)";
        primaryJdbcTemplate.update(sql, userId);
    }
    @Override
    public void applyGameResult(UUID userId, int position, int points, boolean won) {
        String sql = "UPDATE user_stats SET " +
                "avg_position = (avg_position * games_played + ?) / (games_played + 1), " +
                "avg_points = (avg_points * games_played + ?) / (games_played + 1), " +
                "highest_score = GREATEST(highest_score, ?), " +
                "games_won = games_won + CASE WHEN ? THEN 1 ELSE 0 END, " +
                "games_played = games_played + 1, " +
                "updated_at = now() " +
                "WHERE user_id = ?";
        primaryJdbcTemplate.update(sql, position, points, points, won, userId);
    }

    @Override
    public boolean isGameProcessed(String roomId) {
        String sql = "SELECT EXISTS(SELECT 1 FROM processed_games WHERE room_id = ?)";
        Boolean result = primaryJdbcTemplate.queryForObject(sql, Boolean.class, roomId);
        return result != null && result;
    }

    @Override
    public void markGameProcessed(String roomId) {
        String sql = "INSERT INTO processed_games (room_id) VALUES (?)";
        primaryJdbcTemplate.update(sql, roomId);
    }
}
