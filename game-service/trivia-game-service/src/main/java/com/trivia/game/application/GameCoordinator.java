package com.trivia.game.application;

import com.trivia.game.config.GameProperties;
import com.trivia.game.domain.CreditDistributor;
import com.trivia.game.domain.GameException;
import com.trivia.game.domain.PlayerMeta;
import com.trivia.game.domain.PlayerScore;
import com.trivia.game.domain.Question;
import com.trivia.game.domain.RankedPlayer;
import com.trivia.game.domain.RoomSnapshot;
import com.trivia.game.domain.RoomStatus;
import com.trivia.game.domain.RoundCredit;
import com.trivia.game.domain.Theme;
import com.trivia.game.infra.events.RoomEventBus;
import com.trivia.game.infra.kafka.GameFinishedEvent;
import com.trivia.game.infra.kafka.GameFinishedPublisher;
import com.trivia.game.infra.questions.QuestionRepository;
import com.trivia.game.infra.questions.ShardUnavailableException;
import com.trivia.game.infra.redis.RoomRedisRepository;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.scheduling.TaskScheduler;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.security.SecureRandom;
import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ScheduledFuture;

@Service
public class GameCoordinator {
    private static final char[] ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789".toCharArray();
    private static final int ROOM_CODE_LENGTH = 6;

    private final RoomRedisRepository rooms;
    private final QuestionRepository questions;
    private final RoomEventBus events;
    private final GameFinishedPublisher finishedPublisher;
    private final GameProperties properties;
    private final TaskScheduler scheduler;
    private final Clock clock;
    private final SecureRandom random = new SecureRandom();
    private final String instanceId = UUID.randomUUID().toString();

    private final ConcurrentHashMap<String, LeaseTasks> leadership = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Map<UUID, Question>> questionCache = new ConcurrentHashMap<>();

    public GameCoordinator(
            RoomRedisRepository rooms,
            QuestionRepository questions,
            RoomEventBus events,
            GameFinishedPublisher finishedPublisher,
            GameProperties properties,
            @Qualifier("gameTaskScheduler") TaskScheduler scheduler,
            Clock clock
    ) {
        this.rooms = rooms;
        this.questions = questions;
        this.events = events;
        this.finishedPublisher = finishedPublisher;
        this.properties = properties;
        this.scheduler = scheduler;
        this.clock = clock;
    }

    public String createRoom(String creatorId, String creatorName, boolean anonymous, int maxPlayers, int numQuestions, String themeValue) {
        requireText(creatorId, "creator_id é obrigatório");
        requireText(creatorName, "creator_name é obrigatório");
        if (maxPlayers < 2 || maxPlayers > 10) {
            throw GameException.invalidArgument("max_players deve estar entre 2 e 10");
        }
        if (numQuestions < 5 || numQuestions > 20) {
            throw GameException.invalidArgument("num_questions deve estar entre 5 e 20");
        }
        Theme theme = Theme.from(themeValue);
        if (!questions.isAvailable(theme)) {
            throw GameException.unavailable("Shard do tema indisponivel");
        }

        PlayerMeta creator = new PlayerMeta(creatorId, creatorName, anonymous);
        for (int attempt = 0; attempt < 20; attempt++) {
            String roomCode = nextRoomCode();
            if (rooms.createRoom(roomCode, creator, maxPlayers, numQuestions, theme, properties.roomTtlSeconds())) {
                return roomCode;
            }
        }
        throw GameException.precondition("Não foi possível gerar um código de sala único");
    }

    public RoomSnapshot joinRoom(String roomCode, String playerId, String playerName, boolean anonymous) {
        requireText(playerId, "player_id é obrigatório");
        requireText(playerName, "player_name é obrigatório");
        var result = rooms.joinRoom(roomCode, new PlayerMeta(playerId, playerName, anonymous), properties.roomTtlSeconds());
        switch (result) {
            case ROOM_NOT_FOUND -> throw GameException.notFound("Sala não encontrada");
            case NOT_WAITING -> throw GameException.precondition("Sala não está aguardando jogadores");
            case ROOM_FULL -> throw GameException.precondition("Sala atingiu o limite de jogadores");
            case JOINED, ALREADY_JOINED -> {
                RoomSnapshot room = rooms.getRoom(roomCode);
                room.players().stream()
                        .filter(candidate -> candidate.playerId().equals(playerId))
                        .findFirst()
                        .ifPresent(player -> events.broadcast(
                                roomCode,
                                playerJoinedEvent(player.playerId(), player.playerName(), room.players())
                        ));
                return room;
            }
        }
        throw new IllegalStateException("Resultado de entrada inesperado");
    }

    public boolean startGame(String roomCode, String requesterId) {
        return prepareAndStart(roomCode, requesterId, null, RoomStatus.WAITING, false);
    }

    public boolean restartGame(String roomCode, String requesterId, String newTheme) {
        return prepareAndStart(roomCode, requesterId, newTheme, RoomStatus.FINISHED, true);
    }

    public RoomSnapshot getRoom(String roomCode) {
        return rooms.getRoom(roomCode);
    }

    public boolean canConnect(String roomCode, String playerId) {
        return rooms.findRoom(roomCode).map(room -> room.isParticipant(playerId)).orElse(false);
    }

    public void playerSubscribed(String roomCode, String playerId) {
        RoomSnapshot room = rooms.findRoom(roomCode).orElse(null);
        if (room == null) {
            events.sendPrivate(playerId, roomCode, errorEvent("ROOM_NOT_FOUND", "Sala nao encontrada"));
            return;
        }
        PlayerScore player = room.players().stream()
                .filter(candidate -> candidate.playerId().equals(playerId))
                .findFirst()
                .orElse(null);
        if (player == null) {
            return;
        }
        events.broadcast(roomCode, playerJoinedEvent(player.playerId(), player.playerName(), room.players()));
        if (room.status() == RoomStatus.FINISHED) {
            events.broadcast(roomCode, gameOverEvent(ranking(room.players())));
        }
    }

    public void playerConnected(String roomCode, String playerId) {
        RoomSnapshot room = rooms.findRoom(roomCode).orElse(null);
        if (room == null) {
            events.sendPrivate(playerId, roomCode, errorEvent("ROOM_NOT_FOUND", "Sala não encontrada"));
            return;
        }
        if (room.status() == RoomStatus.FINISHED) {
            events.sendPrivate(playerId, roomCode, gameOverEvent(ranking(room.players())));
            return;
        }
        if (room.status() != RoomStatus.IN_PROGRESS || room.roundDeadline() == null || room.runId() == null) {
            return;
        }
        activateLeadership(room, false);
        long remaining = Math.max(0, Duration.between(Instant.now(clock), room.roundDeadline()).toMillis());
        if (remaining > 0) {
            Question question = questionFor(room);
            if (question != null) {
                events.sendPrivate(playerId, roomCode, questionEvent(room, question, remaining));
            }
        }
    }

    public void submitAnswer(String roomCode, String playerId, AnswerCommand answer) {
        RoomSnapshot room = rooms.findRoom(roomCode).orElse(null);
        if (room == null) {
            events.sendPrivate(playerId, roomCode, errorEvent("ROOM_NOT_FOUND", "Sala não encontrada"));
            return;
        }
        if (!room.isParticipant(playerId) || room.status() != RoomStatus.IN_PROGRESS || room.roundDeadline() == null) {
            return;
        }
        Instant receivedAt = Instant.now(clock);
        if (receivedAt.isAfter(room.roundDeadline())) {
            return;
        }
        Question question = questionFor(room);
        if (question == null || answer == null || !"answer".equals(answer.type())
                || !question.id().equals(answer.questionId()) || !question.isValidOption(answer.option())) {
            return;
        }
        boolean firstAttempt = rooms.recordAnswerAttempt(roomCode, room.currentQuestionIdx(), playerId, receivedAt, properties.roomTtlSeconds());
        if (!firstAttempt) {
            return;
        }
        if (question.isCorrect(answer.option())) {
            rooms.recordCorrectAnswer(roomCode, room.currentQuestionIdx(), playerId, receivedAt, properties.roomTtlSeconds());
        }
        if (rooms.answerAttemptCount(roomCode, room.currentQuestionIdx()) >= room.players().size()) {
            activateLeadership(room, false);
            finishRound(roomCode, room.runId(), room.currentQuestionIdx(), true);
        }
    }

    @Scheduled(fixedDelayString = "${game.recovery-scan-ms:1000}")
    public void recoverUnownedRooms() {
        for (String roomCode : rooms.roomsInProgress()) {
            rooms.findRoom(roomCode).ifPresent(room -> activateLeadership(room, true));
        }
    }

    private boolean prepareAndStart(String roomCode, String requesterId, String requestedTheme, RoomStatus expectedStatus, boolean resetScores) {
        requireText(requesterId, "requester_id é obrigatório");
        RoomSnapshot before = rooms.getRoom(roomCode);
        if (!before.creatorId().equals(requesterId)) {
            throw GameException.forbidden("Somente o criador pode iniciar a partida");
        }
        if (before.status() != expectedStatus) {
            throw GameException.precondition("Transição de estado inválida");
        }
        Theme theme = requestedTheme == null || requestedTheme.isBlank() ? before.theme() : Theme.from(requestedTheme);
        List<Question> selected;
        try {
            selected = questions.randomQuestions(theme, before.numQuestions());
        } catch (ShardUnavailableException exception) {
            throw GameException.unavailable("Shard do tema indisponivel");
        }
        if (selected.size() != before.numQuestions()) {
            throw GameException.precondition("Não há perguntas suficientes para iniciar a partida");
        }

        UUID runId = UUID.randomUUID();
        Instant deadline = Instant.now(clock).plusMillis(properties.questionTimeoutMs());
        var result = rooms.prepareGame(roomCode, requesterId, expectedStatus, theme, selected, runId, deadline, resetScores, properties.roomTtlSeconds());
        switch (result) {
            case ROOM_NOT_FOUND -> throw GameException.notFound("Sala não encontrada");
            case FORBIDDEN -> throw GameException.forbidden("Somente o criador pode iniciar a partida");
            case INVALID_STATE -> throw GameException.precondition("Transição de estado inválida");
            case NOT_ENOUGH_PLAYERS -> throw GameException.precondition("São necessários ao menos dois jogadores");
            case STARTED -> {
                RoomSnapshot started = rooms.getRoom(roomCode);
                questionCache.put(cacheKey(started), byId(selected));
                cancelLeadership(roomCode, false);
                activateLeadership(started, false);
                events.broadcast(roomCode, gameStartedEvent(started));
                Question firstQuestion = questionFor(started);
                if (firstQuestion != null) {
                    events.broadcast(roomCode, questionEvent(started, firstQuestion, properties.questionTimeoutMs()));
                }
                return true;
            }
        }
        throw new IllegalStateException("Resultado de preparação inesperado");
    }

    private void activateLeadership(RoomSnapshot room, boolean rebroadcastOnClaim) {
        if (room.status() != RoomStatus.IN_PROGRESS || room.runId() == null || room.roundDeadline() == null) {
            return;
        }
        LeaseTasks active = leadership.get(room.roomCode());
        if (active != null && active.runId.equals(room.runId()) && rooms.ownsLeader(room.roomCode(), active.owner)) {
            scheduleDeadline(active, room.roundDeadline(), room.currentQuestionIdx());
            return;
        }
        String owner = instanceId + ":" + room.runId();
        Duration lease = Duration.ofMillis(properties.leaderLeaseMs());
        if (!rooms.claimLeader(room.roomCode(), owner, lease)) {
            return;
        }
        cancelLeadership(room.roomCode(), false);
        LeaseTasks claimed = new LeaseTasks(room.roomCode(), room.runId(), owner);
        leadership.put(room.roomCode(), claimed);
        long renewalMs = Math.max(250, properties.leaderLeaseMs() / 3);
        claimed.renewalTask = scheduler.scheduleAtFixedRate(() -> renewLeadership(claimed), renewalMs);
        scheduleDeadline(claimed, room.roundDeadline(), room.currentQuestionIdx());
        if (rebroadcastOnClaim) {
            Question question = questionFor(room);
            if (question != null) {
                long remaining = Math.max(0, Duration.between(Instant.now(clock), room.roundDeadline()).toMillis());
                events.broadcast(room.roomCode(), questionEvent(room, question, remaining));
            }
        }
    }

    private void renewLeadership(LeaseTasks tasks) {
        if (!rooms.renewLeader(tasks.roomCode, tasks.owner, Duration.ofMillis(properties.leaderLeaseMs()))) {
            cancelLeadership(tasks.roomCode, false);
        }
    }

    private void scheduleDeadline(LeaseTasks tasks, Instant deadline, int questionIdx) {
        if (tasks.deadlineTask != null && !tasks.deadlineTask.isDone()) {
            tasks.deadlineTask.cancel(false);
        }
        tasks.deadlineTask = scheduler.schedule(() -> finishRound(tasks.roomCode, tasks.runId, questionIdx, false), java.util.Date.from(deadline));
    }

    private void finishRound(String roomCode, UUID scheduledRunId, int expectedQuestionIdx, boolean allowBeforeDeadline) {
        RoomSnapshot before = rooms.findRoom(roomCode).orElse(null);
        if (before == null || before.status() != RoomStatus.IN_PROGRESS || !scheduledRunId.equals(before.runId())
                || before.currentQuestionIdx() != expectedQuestionIdx || before.roundDeadline() == null) {
            return;
        }
        if (!allowBeforeDeadline && Instant.now(clock).isBefore(before.roundDeadline())) {
            LeaseTasks tasks = leadership.get(roomCode);
            if (tasks != null) {
                scheduleDeadline(tasks, before.roundDeadline(), before.currentQuestionIdx());
            }
            return;
        }
        LeaseTasks tasks = leadership.get(roomCode);
        if (tasks == null || !rooms.ownsLeader(roomCode, tasks.owner)
                || !rooms.beginFinalization(roomCode, before.currentQuestionIdx(), before.runId(), Duration.ofMillis(properties.leaderLeaseMs()))) {
            return;
        }

        Question answeredQuestion = questionFor(before);
        List<RoundCredit> credits = CreditDistributor.distribute(rooms.answers(roomCode, before.currentQuestionIdx()));
        Instant nextDeadline = Instant.now(clock).plusMillis(properties.questionTimeoutMs());
        RoomSnapshot after = rooms.applyRound(roomCode, before, credits, nextDeadline, properties.roomTtlSeconds());
        events.broadcast(roomCode, roundResultEvent(answeredQuestion, credits, after.players()));

        if (after.status() == RoomStatus.FINISHED) {
            List<RankedPlayer> ranking = ranking(after.players());
            events.broadcast(roomCode, gameOverEvent(ranking));
            finishedPublisher.publish(roomCode, finishedEvent(after, ranking));
            cancelLeadership(roomCode, true);
            questionCache.remove(cacheKey(before));
            return;
        }

        Question nextQuestion = questionFor(after);
        if (nextQuestion != null) {
            events.broadcast(roomCode, questionEvent(after, nextQuestion, properties.questionTimeoutMs()));
        }
        LeaseTasks leader = leadership.get(roomCode);
        if (leader != null) {
            scheduleDeadline(leader, after.roundDeadline(), after.currentQuestionIdx());
        }
    }

    private Question questionFor(RoomSnapshot room) {
        if (room.currentQuestionIdx() < 0 || room.currentQuestionIdx() >= room.questionIds().size()) {
            return null;
        }
        return questionsFor(room).get(room.questionIds().get(room.currentQuestionIdx()));
    }

    private Map<UUID, Question> questionsFor(RoomSnapshot room) {
        return questionCache.computeIfAbsent(cacheKey(room), ignored -> rooms.questions(room.roomCode()));
    }

    private void cancelLeadership(String roomCode, boolean release) {
        LeaseTasks tasks = leadership.remove(roomCode);
        if (tasks == null) {
            return;
        }
        if (tasks.renewalTask != null) {
            tasks.renewalTask.cancel(false);
        }
        if (tasks.deadlineTask != null) {
            tasks.deadlineTask.cancel(false);
        }
        if (release) {
            rooms.releaseLeader(roomCode, tasks.owner);
        }
    }

    private Map<UUID, Question> byId(List<Question> questions) {
        var values = new LinkedHashMap<UUID, Question>();
        questions.forEach(question -> values.put(question.id(), question));
        return Map.copyOf(values);
    }

    private List<RankedPlayer> ranking(List<PlayerScore> players) {
        var ordered = players.stream()
                .sorted(Comparator.comparingInt(PlayerScore::score).reversed().thenComparing(PlayerScore::playerId))
                .toList();
        var ranking = new ArrayList<RankedPlayer>(ordered.size());
        for (int index = 0; index < ordered.size(); index++) {
            PlayerScore player = ordered.get(index);
            ranking.add(new RankedPlayer(player.playerId(), player.playerName(), player.anonymous(), player.score(), index + 1));
        }
        return List.copyOf(ranking);
    }

    private Map<String, Object> playerJoinedEvent(String playerId, String playerName, List<PlayerScore> players) {
        var event = new LinkedHashMap<String, Object>();
        event.put("type", "player_joined");
        event.put("player_id", playerId);
        event.put("player_name", playerName);
        event.put("players", playerPayload(players));
        return event;
    }

    private Map<String, Object> gameStartedEvent(RoomSnapshot room) {
        return Map.of("type", "game_started", "total_questions", room.numQuestions(), "theme", room.theme().value());
    }

    private Map<String, Object> questionEvent(RoomSnapshot room, Question question, long remainingMs) {
        var event = new LinkedHashMap<String, Object>();
        event.put("type", "question");
        event.put("idx", room.currentQuestionIdx() + 1);
        event.put("question_id", question.id().toString());
        event.put("text", question.text());
        event.put("options", question.options());
        event.put("time_limit_ms", properties.questionTimeoutMs());
        event.put("remaining_time_ms", Math.max(0, remainingMs));
        return event;
    }

    private Map<String, Object> roundResultEvent(Question question, List<RoundCredit> credits, List<PlayerScore> scores) {
        var event = new LinkedHashMap<String, Object>();
        event.put("type", "round_result");
        event.put("question_id", question == null ? "" : question.id().toString());
        event.put("correct_option", question == null ? "" : question.correctOption());
        event.put("credits", credits.stream().map(credit -> Map.of(
                "player_id", credit.playerId(), "earned", credit.earned(), "position", credit.position())).toList());
        event.put("scores", scores.stream().map(score -> Map.of(
                "player_id", score.playerId(), "player_name", score.playerName(), "total_score", score.score())).toList());
        return event;
    }

    private Map<String, Object> gameOverEvent(List<RankedPlayer> ranking) {
        return Map.of("type", "game_over", "ranking", ranking.stream().map(player -> Map.of(
                "player_id", player.playerId(), "player_name", player.playerName(),
                "total_score", player.totalScore(), "position", player.position())).toList());
    }

    private GameFinishedEvent finishedEvent(RoomSnapshot room, List<RankedPlayer> ranking) {
        return new GameFinishedEvent(room.roomCode(), Instant.now(clock), room.theme().value(), room.numQuestions(), ranking.stream()
                .map(player -> new GameFinishedEvent.Result(player.playerId(), player.playerName(), player.anonymous(),
                        player.totalScore(), player.position(), player.position() == 1))
                .toList());
    }

    private List<Map<String, Object>> playerPayload(List<PlayerScore> players) {
        return players.stream().map(player -> Map.<String, Object>of(
                "player_id", player.playerId(), "player_name", player.playerName(),
                "is_anonymous", player.anonymous(), "score", player.score())).toList();
    }

    private Map<String, Object> errorEvent(String code, String message) {
        return Map.of("type", "error", "code", code, "message", message);
    }

    private String nextRoomCode() {
        char[] characters = new char[ROOM_CODE_LENGTH];
        for (int index = 0; index < characters.length; index++) {
            characters[index] = ROOM_CODE_ALPHABET[random.nextInt(ROOM_CODE_ALPHABET.length)];
        }
        return new String(characters);
    }

    private String cacheKey(RoomSnapshot room) {
        return room.roomCode() + ":" + room.runId();
    }

    private static void requireText(String value, String message) {
        if (value == null || value.isBlank()) {
            throw GameException.invalidArgument(message);
        }
    }

    private static final class LeaseTasks {
        private final String roomCode;
        private final UUID runId;
        private final String owner;
        private ScheduledFuture<?> renewalTask;
        private ScheduledFuture<?> deadlineTask;

        private LeaseTasks(String roomCode, UUID runId, String owner) {
            this.roomCode = roomCode;
            this.runId = runId;
            this.owner = owner;
        }
    }
}

