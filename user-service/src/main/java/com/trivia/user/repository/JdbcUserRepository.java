package com.trivia.user.repository;

import com.trivia.user.domain.User;
import com.trivia.user.exception.AlreadyExistsException;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.support.GeneratedKeyHolder;
import org.springframework.jdbc.support.KeyHolder;
import org.springframework.stereotype.Repository;

import java.sql.PreparedStatement;
import java.util.Optional;
import java.util.UUID;

@Repository
public class JdbcUserRepository implements UserRepository {

    private static final RowMapper<User> USER_ROW_MAPPER = (rs, rowNum) -> new User(
            UUID.fromString(rs.getString("id")),
            rs.getString("name"),
            rs.getString("password_hash")
    );

    private final JdbcTemplate primaryJdbcTemplate;
    private final JdbcTemplate replicaJdbcTemplate;

    public JdbcUserRepository(@Qualifier("primaryJdbcTemplate") JdbcTemplate primaryJdbcTemplate,
                              @Qualifier("replicaJdbcTemplate") JdbcTemplate replicaJdbcTemplate) {
        this.primaryJdbcTemplate = primaryJdbcTemplate;
        this.replicaJdbcTemplate = replicaJdbcTemplate;
    }

    @Override
    public UUID insert(String name, String passwordHash) {
        String sql = "INSERT INTO users (name, password_hash) VALUES (?, ?)";
        KeyHolder keyHolder = new GeneratedKeyHolder();

        try {
            primaryJdbcTemplate.update(connection -> {
                PreparedStatement ps = connection.prepareStatement(sql, new String[]{"id"});
                ps.setString(1, name);
                ps.setString(2, passwordHash);
                return ps;
            }, keyHolder);
        } catch (DataIntegrityViolationException e) {
            throw new AlreadyExistsException("name already registered: " + name);
        }

        return UUID.fromString(keyHolder.getKeys().get("id").toString());
    }

    @Override
    public Optional<User> findByName(String name) {
        String sql = "SELECT id, name, password_hash FROM users WHERE name = ?";
        Optional<User> replicaUser = findOne(replicaJdbcTemplate, sql, name);
        return replicaUser.or(() -> findOne(primaryJdbcTemplate, sql, name));
    }

    @Override
    public Optional<User> findById(UUID userId) {
        String sql = "SELECT id, name, password_hash FROM users WHERE id = ?";
        Optional<User> replicaUser = findOne(replicaJdbcTemplate, sql, userId);
        return replicaUser.or(() -> findOne(primaryJdbcTemplate, sql, userId));
    }

    @Override
    public void updateName(UUID userId, String newName) {
        String sql = "UPDATE users SET name = ? WHERE id = ?";
        try {
            primaryJdbcTemplate.update(sql, newName, userId);
        } catch (DataIntegrityViolationException e) {
            throw new AlreadyExistsException("name already in use: " + newName);
        }
    }

    @Override
    public void updatePasswordHash(UUID userId, String newPasswordHash) {
        String sql = "UPDATE users SET password_hash = ? WHERE id = ?";
        primaryJdbcTemplate.update(sql, newPasswordHash, userId);
    }

    @Override
    public boolean existsByName(String name) {
        String sql = "SELECT EXISTS(SELECT 1 FROM users WHERE name = ?)";
        Boolean result = primaryJdbcTemplate.queryForObject(sql, Boolean.class, name);
        return result != null && result;
    }

    private Optional<User> findOne(JdbcTemplate jdbcTemplate, String sql, Object argument) {
        return jdbcTemplate.query(sql, USER_ROW_MAPPER, argument)
                .stream()
                .findFirst();
    }
}
