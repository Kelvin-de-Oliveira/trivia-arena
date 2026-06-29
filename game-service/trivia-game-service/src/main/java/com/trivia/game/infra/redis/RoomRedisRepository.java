package com.trivia.game.infra.redis;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trivia.game.domain.PlayerMeta;
import com.trivia.game.domain.PlayerScore;
import com.trivia.game.domain.Question;
import com.trivia.game.domain.RoomSnapshot;
import com.trivia.game.domain.RoomStatus;
import com.trivia.game.domain.RoundCredit;
import com.trivia.game.domain.Theme;
import org.springframework.dao.DataAccessException;
import org.springframework.data.redis.core.Cursor;
import org.springframework.data.redis.core.RedisCallback;
import org.springframework.data.redis.core.ScanOptions;
import org.springframework.data.redis.core.SessionCallback;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.script.DefaultRedisScript;
import org.springframework.stereotype.Repository;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Repository
public class RoomRedisRepository {
    public enum JoinResult { JOINED, ALREADY_JOINED, ROOM_NOT_FOUND, NOT_WAITING, ROOM_FULL }
    public enum PrepareResult { STARTED, ROOM_NOT_FOUND, FORBIDDEN, INVALID_STATE, NOT_ENOUGH_PLAYERS }

    private static final DefaultRedisScript<Long> CREATE_ROOM = new DefaultRedisScript<>("""
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            redis.call('HSET', KEYS[1], 'status', 'WAITING', 'creator_id', ARGV[1],
              'max_players', ARGV[2], 'num_questions', ARGV[3], 'theme', ARGV[4],
              'current_question_idx', '0', 'question_ids', '', 'run_id', '', 'round_deadline_at', '')
            redis.call('HSET', KEYS[2], ARGV[1], '0')
            redis.call('HSET', KEYS[3], ARGV[1], ARGV[5])
            redis.call('EXPIRE', KEYS[1], ARGV[6])
            redis.call('EXPIRE', KEYS[2], ARGV[6])
            redis.call('EXPIRE', KEYS[3], ARGV[6])
            return 1
            """, Long.class);

    private static final DefaultRedisScript<Long> JOIN_ROOM = new DefaultRedisScript<>("""
            if redis.call('EXISTS', KEYS[1]) == 0 then return -1 end
            if redis.call('HGET', KEYS[1], 'status') ~= 'WAITING' then return -2 end
            if redis.call('HEXISTS', KEYS[2], ARGV[1]) == 1 then return 1 end
            if redis.call('HLEN', KEYS[2]) >= tonumber(redis.call('HGET', KEYS[1], 'max_players')) then return -3 end
            redis.call('HSET', KEYS[2], ARGV[1], '0')
            redis.call('HSET', KEYS[3], ARGV[1], ARGV[2])
            redis.call('EXPIRE', KEYS[1], ARGV[3])
            redis.call('EXPIRE', KEYS[2], ARGV[3])
            redis.call('EXPIRE', KEYS[3], ARGV[3])
            return 0
            """, Long.class);

    private static final DefaultRedisScript<Long> PREPARE_GAME = new DefaultRedisScript<>("""
            if redis.call('EXISTS', KEYS[1]) == 0 then return -1 end
            if redis.call('HGET', KEYS[1], 'creator_id') ~= ARGV[1] then return -2 end
            if redis.call('HGET', KEYS[1], 'status') ~= ARGV[2] then return -3 end
            if redis.call('HLEN', KEYS[2]) < 2 then return -4 end
            for i = 5, #KEYS do redis.call('DEL', KEYS[i]) end
            redis.call('DEL', KEYS[4])
            redis.call('DEL', KEYS[3])
            local itemStart = 9
            for i = itemStart, #ARGV, 2 do redis.call('HSET', KEYS[3], ARGV[i], ARGV[i + 1]) end
            if ARGV[8] == 'true' then
              local players = redis.call('HKEYS', KEYS[2])
              for _, player in ipairs(players) do redis.call('HSET', KEYS[2], player, '0') end
            end
            redis.call('HSET', KEYS[1], 'status', 'IN_PROGRESS', 'theme', ARGV[3],
              'question_ids', ARGV[4], 'current_question_idx', '0', 'run_id', ARGV[5],
              'round_deadline_at', ARGV[6])
            for i = 1, 3 do redis.call('EXPIRE', KEYS[i], ARGV[7]) end
            return 1
            """, Long.class);

    private static final DefaultRedisScript<Long> COMPARE_AND_EXPIRE = new DefaultRedisScript<>("""
            if redis.call('GET', KEYS[1]) == ARGV[1] then
              return redis.call('PEXPIRE', KEYS[1], ARGV[2])
            end
            return 0
            """, Long.class);

    private static final DefaultRedisScript<Long> COMPARE_AND_DELETE = new DefaultRedisScript<>("""
            if redis.call('GET', KEYS[1]) == ARGV[1] then return redis.call('DEL', KEYS[1]) end
            return 0
            """, Long.class);

    private final StringRedisTemplate redis;
    private final ObjectMapper objectMapper;

    public RoomRedisRepository(StringRedisTemplate redis, ObjectMapper objectMapper) {
        this.redis = redis;
        this.objectMapper = objectMapper;
    }

    public boolean createRoom(String roomCode, PlayerMeta creator, int maxPlayers, int numQuestions, Theme theme, long ttlSeconds) {
        Long created = redis.execute(CREATE_ROOM, List.of(stateKey(roomCode), playersKey(roomCode), playerMetaKey(roomCode)),
                creator.playerId(), String.valueOf(maxPlayers), String.valueOf(numQuestions), theme.value(), toJson(creator), String.valueOf(ttlSeconds));
        return Long.valueOf(1L).equals(created);
    }

    public JoinResult joinRoom(String roomCode, PlayerMeta player, long ttlSeconds) {
        Long result = redis.execute(JOIN_ROOM, List.of(stateKey(roomCode), playersKey(roomCode), playerMetaKey(roomCode)),
                player.playerId(), toJson(player), String.valueOf(ttlSeconds));
        return switch (result == null ? -1 : result.intValue()) {
            case 0 -> JoinResult.JOINED;
            case 1 -> JoinResult.ALREADY_JOINED;
            case -2 -> JoinResult.NOT_WAITING;
            case -3 -> JoinResult.ROOM_FULL;
            default -> JoinResult.ROOM_NOT_FOUND;
        };
    }

    public PrepareResult prepareGame(
            String roomCode,
            String requesterId,
            RoomStatus expectedStatus,
            Theme theme,
            List<Question> questions,
            UUID runId,
            Instant deadline,
            boolean resetScores,
            long ttlSeconds
    ) {
        var keys = new ArrayList<String>();
        keys.add(stateKey(roomCode));
        keys.add(playersKey(roomCode));
        keys.add(questionsKey(roomCode));
        keys.add(leaderKey(roomCode));
        RoomSnapshot before = findRoom(roomCode).orElse(null);
        int answerKeys = before == null ? 20 : before.numQuestions();
        for (int index = 0; index < answerKeys; index++) {
            keys.add(answersKey(roomCode, index));
            keys.add(answerAttemptsKey(roomCode, index));
            keys.add(finalizerKey(roomCode, index));
        }
        var args = new ArrayList<String>();
        args.add(requesterId);
        args.add(expectedStatus.name());
        args.add(theme.value());
        args.add(questions.stream().map(question -> question.id().toString()).reduce((left, right) -> left + "," + right).orElse(""));
        args.add(runId.toString());
        args.add(deadline.toString());
        args.add(String.valueOf(ttlSeconds));
        args.add(String.valueOf(resetScores));
        for (Question question : questions) {
            args.add(question.id().toString());
            args.add(toJson(question));
        }
        Long result = redis.execute(PREPARE_GAME, keys, args.toArray(String[]::new));
        return switch (result == null ? -1 : result.intValue()) {
            case 1 -> PrepareResult.STARTED;
            case -2 -> PrepareResult.FORBIDDEN;
            case -3 -> PrepareResult.INVALID_STATE;
            case -4 -> PrepareResult.NOT_ENOUGH_PLAYERS;
            default -> PrepareResult.ROOM_NOT_FOUND;
        };
    }

    public java.util.Optional<RoomSnapshot> findRoom(String roomCode) {
        Map<Object, Object> state = redis.opsForHash().entries(stateKey(roomCode));
        if (state.isEmpty()) {
            return java.util.Optional.empty();
        }
        Map<Object, Object> scores = redis.opsForHash().entries(playersKey(roomCode));
        Map<Object, Object> metadata = redis.opsForHash().entries(playerMetaKey(roomCode));
        var players = new ArrayList<PlayerScore>();
        for (Map.Entry<Object, Object> score : scores.entrySet()) {
            String playerId = String.valueOf(score.getKey());
            PlayerMeta meta = fromJson(String.valueOf(metadata.get(score.getKey())), PlayerMeta.class);
            if (meta != null) {
                players.add(new PlayerScore(playerId, meta.playerName(), meta.anonymous(), Integer.parseInt(String.valueOf(score.getValue()))));
            }
        }
        players.sort(Comparator.comparing(PlayerScore::playerId));
        String questionIds = get(state, "question_ids");
        List<UUID> ids = questionIds.isBlank() ? List.of() : java.util.Arrays.stream(questionIds.split(",")).map(UUID::fromString).toList();
        String runId = get(state, "run_id");
        String deadline = get(state, "round_deadline_at");
        return java.util.Optional.of(new RoomSnapshot(
                roomCode,
                RoomStatus.valueOf(get(state, "status")),
                get(state, "creator_id"),
                Integer.parseInt(get(state, "max_players")),
                Integer.parseInt(get(state, "num_questions")),
                Theme.from(get(state, "theme")),
                Integer.parseInt(get(state, "current_question_idx")),
                ids,
                runId.isBlank() ? null : UUID.fromString(runId),
                deadline.isBlank() ? null : Instant.parse(deadline),
                List.copyOf(players)
        ));
    }

    public RoomSnapshot getRoom(String roomCode) {
        return findRoom(roomCode).orElseThrow(() -> com.trivia.game.domain.GameException.notFound("Sala não encontrada"));
    }

    public Map<UUID, Question> questions(String roomCode) {
        Map<Object, Object> serialized = redis.opsForHash().entries(questionsKey(roomCode));
        var questions = new LinkedHashMap<UUID, Question>();
        serialized.forEach((id, value) -> questions.put(UUID.fromString(String.valueOf(id)), fromJson(String.valueOf(value), Question.class)));
        return Map.copyOf(questions);
    }

    public boolean recordCorrectAnswer(String roomCode, int questionIdx, String playerId, Instant receivedAt, long ttlSeconds) {
        String key = answersKey(roomCode, questionIdx);
        Boolean added = redis.opsForHash().putIfAbsent(key, playerId, receivedAt.toString());
        if (Boolean.TRUE.equals(added)) {
            redis.expire(key, Duration.ofSeconds(ttlSeconds));
            return true;
        }
        return false;
    }

    public boolean recordAnswerAttempt(String roomCode, int questionIdx, String playerId, Instant receivedAt, long ttlSeconds) {
        String key = answerAttemptsKey(roomCode, questionIdx);
        Boolean added = redis.opsForHash().putIfAbsent(key, playerId, receivedAt.toString());
        if (Boolean.TRUE.equals(added)) {
            redis.expire(key, Duration.ofSeconds(ttlSeconds));
            return true;
        }
        return false;
    }

    public long answerAttemptCount(String roomCode, int questionIdx) {
        Long size = redis.opsForHash().size(answerAttemptsKey(roomCode, questionIdx));
        return size == null ? 0 : size;
    }

    public Map<String, Instant> answers(String roomCode, int questionIdx) {
        Map<Object, Object> stored = redis.opsForHash().entries(answersKey(roomCode, questionIdx));
        var answers = new HashMap<String, Instant>();
        stored.forEach((player, timestamp) -> answers.put(String.valueOf(player), Instant.parse(String.valueOf(timestamp))));
        return Map.copyOf(answers);
    }

    public boolean claimLeader(String roomCode, String owner, Duration lease) {
        return Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(leaderKey(roomCode), owner, lease));
    }

    public boolean renewLeader(String roomCode, String owner, Duration lease) {
        Long renewed = redis.execute(COMPARE_AND_EXPIRE, List.of(leaderKey(roomCode)), owner, String.valueOf(lease.toMillis()));
        return Long.valueOf(1L).equals(renewed);
    }

    public boolean ownsLeader(String roomCode, String owner) {
        return owner.equals(redis.opsForValue().get(leaderKey(roomCode)));
    }

    public void releaseLeader(String roomCode, String owner) {
        redis.execute(COMPARE_AND_DELETE, List.of(leaderKey(roomCode)), owner);
    }

    public boolean beginFinalization(String roomCode, int questionIdx, UUID runId, Duration lease) {
        return Boolean.TRUE.equals(redis.opsForValue().setIfAbsent(finalizerKey(roomCode, questionIdx), runId.toString(), lease));
    }

    public RoomSnapshot applyRound(String roomCode, RoomSnapshot before, List<RoundCredit> credits, Instant nextDeadline, long ttlSeconds) {
        boolean lastQuestion = before.currentQuestionIdx() + 1 >= before.numQuestions();
        redis.execute(new SessionCallback<List<Object>>() {
            @Override
            @SuppressWarnings({"rawtypes", "unchecked"})
            public List<Object> execute(org.springframework.data.redis.core.RedisOperations operations) throws DataAccessException {
                operations.multi();
                for (RoundCredit credit : credits) {
                    operations.opsForHash().increment(playersKey(roomCode), credit.playerId(), credit.earned());
                }
                if (lastQuestion) {
                    operations.opsForHash().put(stateKey(roomCode), "status", RoomStatus.FINISHED.name());
                    operations.opsForHash().put(stateKey(roomCode), "round_deadline_at", "");
                } else {
                    operations.opsForHash().put(stateKey(roomCode), "current_question_idx", String.valueOf(before.currentQuestionIdx() + 1));
                    operations.opsForHash().put(stateKey(roomCode), "round_deadline_at", nextDeadline.toString());
                }
                operations.expire(stateKey(roomCode), Duration.ofSeconds(ttlSeconds));
                operations.expire(playersKey(roomCode), Duration.ofSeconds(ttlSeconds));
                operations.expire(playerMetaKey(roomCode), Duration.ofSeconds(ttlSeconds));
                operations.expire(questionsKey(roomCode), Duration.ofSeconds(ttlSeconds));
                return operations.exec();
            }
        });
        return getRoom(roomCode);
    }

    public List<String> roomsInProgress() {
        List<String> keys = redis.execute((RedisCallback<List<String>>) connection -> {
            var roomStateKeys = new ArrayList<String>();
            try (Cursor<byte[]> cursor = connection.scan(ScanOptions.scanOptions().match("room:*:state").count(100).build())) {
                while (cursor.hasNext()) {
                    roomStateKeys.add(new String(cursor.next(), StandardCharsets.UTF_8));
                }
            }
            return roomStateKeys;
        });
        if (keys == null) {
            return List.of();
        }
        return keys.stream()
                .map(key -> key.substring("room:".length(), key.length() - ":state".length()))
                .filter(code -> findRoom(code).map(room -> room.status() == RoomStatus.IN_PROGRESS).orElse(false))
                .toList();
    }

    private static String get(Map<Object, Object> fields, String key) {
        Object value = fields.get(key);
        return value == null ? "" : String.valueOf(value);
    }

    private String toJson(Object value) {
        try {
            return objectMapper.writeValueAsString(value);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Não foi possível serializar estado da sala", exception);
        }
    }

    private <T> T fromJson(String json, Class<T> type) {
        if (json == null || json.equals("null")) {
            return null;
        }
        try {
            return objectMapper.readValue(json, type);
        } catch (JsonProcessingException exception) {
            throw new IllegalStateException("Estado Redis inválido", exception);
        }
    }

    public static String stateKey(String roomCode) { return "room:%s:state".formatted(roomCode); }
    public static String playersKey(String roomCode) { return "room:%s:players".formatted(roomCode); }
    public static String playerMetaKey(String roomCode) { return "room:%s:player-meta".formatted(roomCode); }
    public static String questionsKey(String roomCode) { return "room:%s:questions".formatted(roomCode); }
    public static String answersKey(String roomCode, int index) { return "room:%s:round:%d:answers".formatted(roomCode, index); }
    public static String answerAttemptsKey(String roomCode, int index) { return "room:%s:round:%d:answer-attempts".formatted(roomCode, index); }
    public static String finalizerKey(String roomCode, int index) { return "room:%s:round:%d:finalizer".formatted(roomCode, index); }
    public static String leaderKey(String roomCode) { return "room:%s:leader".formatted(roomCode); }
    public static String broadcastChannel(String roomCode) { return "room:%s:broadcast".formatted(roomCode); }
}
