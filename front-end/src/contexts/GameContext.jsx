import { useCallback, useMemo, useRef, useState } from 'react';
import { Client } from '@stomp/stompjs';
import { getRoom } from '../api/rooms';
import { GameContext } from './game-context';

const API_GATEWAY_HOST = import.meta.env.VITE_API_GATEWAY_HOST || 'localhost:8000';
const MAX_RECONNECT_ATTEMPTS = 4;

const EMPTY_ROOM = {
  roomCode: '',
  status: 'WAITING',
  theme: '',
  maxPlayers: 0,
  numQuestions: 0,
  totalQuestions: 0,
  creatorId: '',
  players: [],
};

const normalizePlayers = (players = []) => players.map((player) => ({
  player_id: player.player_id,
  player_name: player.player_name,
  is_anonymous: Boolean(player.is_anonymous),
  score: Number(player.score ?? player.total_score ?? 0),
}));

const normalizeQuestion = (event) => ({
  ...event,
  effectiveTimeMs: Number(event.remaining_time_ms ?? event.time_limit_ms ?? 20000),
  receivedAt: Date.now(),
});

const mergeScores = (players, scores = []) => {
  if (!scores.length) return players;

  const existingById = new Map(players.map((player) => [player.player_id, player]));
  return scores.map((score) => {
    const existing = existingById.get(score.player_id);
    return {
      player_id: score.player_id,
      player_name: score.player_name || existing?.player_name || 'Jogador',
      is_anonymous: existing?.is_anonymous ?? false,
      score: Number(score.score ?? score.total_score ?? 0),
    };
  });
};

export const GameProvider = ({ children }) => {
  const [room, setRoom] = useState(EMPTY_ROOM);
  const [connectionStatus, setConnectionStatus] = useState('idle');
  const [connectionMessage, setConnectionMessage] = useState('');
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [selectedOption, setSelectedOption] = useState(null);
  const [roundResult, setRoundResult] = useState(null);
  const [gameOverData, setGameOverData] = useState(null);
  const [error, setError] = useState(null);

  const stompClientRef = useRef(null);
  const reconnectAttemptsRef = useRef(0);
  const manualDisconnectRef = useRef(true);
  const connectionConfigRef = useRef(null);

  const clearError = useCallback(() => setError(null), []);

  const resetRoomState = useCallback((roomCode = '') => {
    setRoom({ ...EMPTY_ROOM, roomCode });
    setConnectionStatus('idle');
    setConnectionMessage('');
    setCurrentQuestion(null);
    setSelectedOption(null);
    setRoundResult(null);
    setGameOverData(null);
    setError(null);
  }, []);

  const setRoomSnapshot = useCallback((roomCode, snapshot) => {
    setRoom((prev) => ({
      ...prev,
      roomCode: snapshot.room_code || roomCode || prev.roomCode,
      status: snapshot.status || prev.status,
      theme: snapshot.theme ?? prev.theme,
      maxPlayers: Number(snapshot.max_players ?? prev.maxPlayers),
      numQuestions: Number(snapshot.num_questions ?? prev.numQuestions),
      totalQuestions: Number(snapshot.num_questions ?? prev.totalQuestions),
      creatorId: snapshot.creator_id ?? prev.creatorId,
      players: normalizePlayers(snapshot.players ?? prev.players),
    }));
  }, []);

  const refreshRoomSnapshot = useCallback(async (roomCode) => {
    try {
      const { data } = await getRoom(roomCode);
      setRoomSnapshot(roomCode, data);
      return data;
    } catch (err) {
      setError({
        code: err.response?.data?.error || 'ROOM_SYNC_FAILED',
        message: err.response?.data?.message || 'Não foi possível recuperar o estado da sala.',
      });
      return null;
    }
  }, [setRoomSnapshot]);

  const applyRoomEvent = useCallback((roomCode, event) => {
    switch (event.type) {
      case 'player_joined': {
        setRoom((prev) => {
          const players = event.players
            ? normalizePlayers(event.players)
            : normalizePlayers([
              ...prev.players,
              {
                player_id: event.player_id,
                player_name: event.player_name,
                is_anonymous: false,
                score: 0,
              },
            ]);

          return {
            ...prev,
            roomCode,
            players,
          };
        });
        break;
      }
      case 'game_started':
        setRoom((prev) => ({
          ...prev,
          roomCode,
          status: 'IN_PROGRESS',
          theme: event.theme ?? prev.theme,
          totalQuestions: Number(event.total_questions ?? prev.totalQuestions),
        }));
        setCurrentQuestion(null);
        setSelectedOption(null);
        setRoundResult(null);
        setGameOverData(null);
        setError(null);
        break;
      case 'question':
        setRoom((prev) => ({ ...prev, roomCode, status: 'IN_PROGRESS' }));
        setCurrentQuestion(normalizeQuestion(event));
        setSelectedOption(null);
        setRoundResult(null);
        setError(null);
        break;
      case 'round_result':
        setRoundResult(event);
        setRoom((prev) => ({
          ...prev,
          roomCode,
          players: mergeScores(prev.players, event.scores),
        }));
        break;
      case 'game_over':
        setRoom((prev) => ({
          ...prev,
          roomCode,
          status: 'FINISHED',
          players: mergeScores(prev.players, event.ranking),
        }));
        setCurrentQuestion(null);
        setSelectedOption(null);
        setRoundResult(null);
        setGameOverData(event);
        setError(null);
        break;
      case 'error':
        setError({
          code: event.code || 'WEBSOCKET_ERROR',
          message: event.message || 'O servidor enviou um erro inesperado.',
        });
        break;
      default:
        break;
    }
  }, []);

  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    reconnectAttemptsRef.current = 0;

    if (stompClientRef.current) {
      stompClientRef.current.deactivate();
      stompClientRef.current = null;
    }

    setConnectionStatus('idle');
    setConnectionMessage('');
  }, []);

  const connectToRoom = useCallback((roomCode, player, jwt) => {
    if (!roomCode || !player?.playerId) return;

    if (stompClientRef.current) {
      const previousClient = stompClientRef.current;
      manualDisconnectRef.current = true;
      previousClient.reconnectDelay = 0;
      previousClient.deactivate();
    }

    const connectHeaders = {
      'player-id': player.playerId,
      'room-code': roomCode,
    };

    if (jwt) {
      connectHeaders.authorization = `Bearer ${jwt}`;
    }

    reconnectAttemptsRef.current = 0;
    manualDisconnectRef.current = false;
    connectionConfigRef.current = { roomCode, player, jwt };
    setConnectionStatus('connecting');
    setConnectionMessage('Conectando à arena...');

    const client = new Client({
      brokerURL: `ws://${API_GATEWAY_HOST}/ws/rooms/${roomCode}`,
      connectHeaders,
      reconnectDelay: 1000,
      debug: () => {},
      onConnect: () => {
        if (stompClientRef.current !== client) {
          return;
        }

        reconnectAttemptsRef.current = 0;
        setConnectionStatus('connected');
        setConnectionMessage('Conectado');
        const handleRoomMessage = (message) => {
          try {
            applyRoomEvent(roomCode, JSON.parse(message.body));
          } catch {
            setError({
              code: 'INVALID_EVENT',
              message: 'Não foi possível ler uma atualização da partida.',
            });
          }
        };

        client.subscribe(`/topic/rooms/${roomCode}`, handleRoomMessage);

        refreshRoomSnapshot(roomCode);
      },
      onWebSocketClose: () => {
        if (manualDisconnectRef.current || stompClientRef.current !== client) {
          return;
        }

        const nextAttempt = reconnectAttemptsRef.current + 1;
        reconnectAttemptsRef.current = nextAttempt;

        if (nextAttempt > MAX_RECONNECT_ATTEMPTS) {
          manualDisconnectRef.current = true;
          client.reconnectDelay = 0;
          client.deactivate();
          setConnectionStatus('failed');
          setConnectionMessage('Conexão perdida. Tente reconectar manualmente.');
          return;
        }

        const delay = Math.min(8000, 1000 * (2 ** (nextAttempt - 1)));
        client.reconnectDelay = delay;
        setConnectionStatus('reconnecting');
        setConnectionMessage(`Reconectando em ${delay / 1000}s...`);
      },
      onWebSocketError: () => {
        if (stompClientRef.current !== client) {
          return;
        }

        setError({
          code: 'WEBSOCKET_ERROR',
          message: 'A conexão em tempo real falhou.',
        });
      },
      onStompError: (frame) => {
        if (stompClientRef.current !== client) {
          return;
        }

        setError({
          code: 'STOMP_ERROR',
          message: frame.headers?.message || 'O servidor recusou a conexão da sala.',
        });
      },
    });

    stompClientRef.current = client;
    client.activate();
  }, [applyRoomEvent, refreshRoomSnapshot]);

  const reconnect = useCallback(() => {
    const config = connectionConfigRef.current;
    if (config) {
      connectToRoom(config.roomCode, config.player, config.jwt);
    }
  }, [connectToRoom]);

  const sendAnswer = useCallback((roomCode, option) => {
    if (!currentQuestion || selectedOption) return false;

    const client = stompClientRef.current;
    if (!client?.connected) {
      setError({
        code: 'NOT_CONNECTED',
        message: 'Reconecte antes de responder.',
      });
      return false;
    }

    client.publish({
      destination: `/app/rooms/${roomCode}/answer`,
      body: JSON.stringify({
        type: 'answer',
        question_id: currentQuestion.question_id,
        option,
      }),
    });

    setSelectedOption(option);
    return true;
  }, [currentQuestion, selectedOption]);

  const value = useMemo(() => ({
    room,
    players: room.players,
    connectionStatus,
    connectionMessage,
    currentQuestion,
    selectedOption,
    roundResult,
    gameOverData,
    error,
    setRoomSnapshot,
    resetRoomState,
    connectToRoom,
    disconnect,
    reconnect,
    sendAnswer,
    clearError,
    refreshRoomSnapshot,
  }), [
    room,
    connectionStatus,
    connectionMessage,
    currentQuestion,
    selectedOption,
    roundResult,
    gameOverData,
    error,
    setRoomSnapshot,
    resetRoomState,
    connectToRoom,
    disconnect,
    reconnect,
    sendAnswer,
    clearError,
    refreshRoomSnapshot,
  ]);

  return (
    <GameContext.Provider value={value}>
      {children}
    </GameContext.Provider>
  );
};
