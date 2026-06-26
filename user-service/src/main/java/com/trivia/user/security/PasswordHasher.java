package com.trivia.user.security;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.stereotype.Component;

@Component
public class PasswordHasher {

    private final BCryptPasswordEncoder encoder;

    public PasswordHasher(@Value("${bcrypt.strength:10}") int strength) {
        this.encoder = new BCryptPasswordEncoder(strength);
    }

    public String hash(String plainPassword) {
        return encoder.encode(plainPassword);
    }

    public boolean matches(String plainPassword, String storedHash) {
        return encoder.matches(plainPassword, storedHash);
    }
}