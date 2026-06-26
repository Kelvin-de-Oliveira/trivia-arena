import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { GameProvider } from './contexts/GameContext';

const Home = () => <div>Tela: Home / Entrada</div>;
const Login = () => <div>Tela: Login</div>;
const Register = () => <div>Tela: Cadastro</div>;
const Profile = () => <div>Tela: Perfil e Estatísticas</div>;
const CreateRoom = () => <div>Tela: Criar Sala</div>;
const Room = () => <div>Tela: Lobby / Partida em Andamento</div>;

const ProtectedRoute = ({ children }) => {
  const { user } = useAuth();
  
  if (!user || user.isAnonymous) {
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

const App = () => {
  return (
    <AuthProvider>
      <GameProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            
            <Route path="/room/create" element={<CreateRoom />} />
            <Route path="/room/:roomCode" element={<Room />} />
            
            <Route 
              path="/profile" 
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              } 
            />
          </Routes>
        </BrowserRouter>
      </GameProvider>
    </AuthProvider>
  );
};

export default App;