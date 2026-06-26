CREATE TABLE users (
                       id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
                       name          TEXT        NOT NULL UNIQUE,
                       password_hash TEXT        NOT NULL,
                       created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_name ON users (name);

CREATE TABLE user_stats (
                            user_id       UUID        PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                            games_played  INT         NOT NULL DEFAULT 0,
                            games_won     INT         NOT NULL DEFAULT 0,
                            avg_position  DOUBLE PRECISION NOT NULL DEFAULT 0,
                            avg_points    DOUBLE PRECISION NOT NULL DEFAULT 0,
                            highest_score INT         NOT NULL DEFAULT 0,
                            updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE processed_games (
                                 room_id       TEXT        PRIMARY KEY,
                                 processed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);