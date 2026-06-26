package com.trivia.user.repository;

import com.trivia.user.domain.User;

import java.util.Optional;
import java.util.UUID;

public interface UserRepository {

    UUID insert(String name, String passwordHash);

    Optional<User> findByName(String name);

    Optional<User> findById(UUID userId);

    void updateName(UUID userId, String newName);

    void updatePasswordHash(UUID userId, String newPasswordHash);

    boolean existsByName(String name);
}