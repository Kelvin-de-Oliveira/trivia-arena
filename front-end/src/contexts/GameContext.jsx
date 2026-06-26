import React, { createContext, useState, useContext, useCallback, useRef } from 'react';
import { Client } from '@stomp/stompjs';

const GameContext = createContext(null);

export const GameProvider = ({ children }) => {
  const [gameState, setGameState] = useState('WAITING');
  const [players, setPlayers] = useState([]);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [roundResult, setRoundResult] = useState(null);
  const [gameOverData, setGameOverData] = useState(null);
  
  const stompClientRef = useRef(null);

  const connectToRoom = useCallback((roomCode, playerId, jwt) => {
    const host = import.meta.env.VITE_API_GATEWAY_HOST || 'localhost:8000';
    const brokerURL = `ws://${host}/ws/rooms/${roomCode}`;

    const connectHeaders = {
      'player-id': playerId,
      'room-code': roomCode,
    };

    if (jwt) {
      connectHeaders['authorization'] = `Bearer ${jwt}`;
    }

    const client = new Client({
      brokerURL,
      connectHeaders,
      reconnectDelay: 1000,
      
      onConnect: () => {
        client.subscribe(`/topic/rooms/${roomCode}`, (message) => {
          const body = JSON.parse(message.body);
          
          switch (body.type) {
            case 'player_joined':
              setPlayers((prev) => [...prev, body.player]);
              break;
            case 'game_started':
              setGameState('IN_PROGRESS');
              break;
            case 'question':
              setCurrentQuestion(body);
              setRoundResult(null);
              break;
            case 'round_result':
              setRoundResult(body);
              break;
            case 'game_over':
              setGameState('FINISHED');
              setGameOverData(body);
              break;
            case 'error':
              console.error('Erro WebSocket:', body.code);
              break;
            default:
              break;
          }
        });
      },
    });

    client.activate();
    stompClientRef.current = client;
  }, []);

  const disconnect = useCallback(() => {
    if (stompClientRef.current) {
      stompClientRef.current.deactivate();
    }
  }, []);

  const sendAnswer = useCallback((roomCode, answerId) => {
    if (stompClientRef.current && stompClientRef.current.connected) {
      stompClientRef.current.publish({
        destination: `/app/rooms/${roomCode}/answer`,
        body: JSON.stringify({ answer_id: answerId }),
      });
    }
  }, []);

  return (
    <GameContext.Provider 
      value={{ 
        gameState, 
        players, 
        currentQuestion, 
        roundResult, 
        gameOverData, 
        connectToRoom, 
        disconnect, 
        sendAnswer 
      }}
    >
      {children}
    </GameContext.Provider>
  );
};

export const useGame = () => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error("useGame deve ser usado dentro de um GameProvider");
  }
  return context;
};