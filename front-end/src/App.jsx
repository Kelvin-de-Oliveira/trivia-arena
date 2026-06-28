import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { GameProvider } from './contexts/GameContext';

import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import Profile from './pages/Profile';
//  CreateRoom from './pages/CreateRoom';
// import Room from './pages/Room';

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
            
            {/*<Route path="/room/create" element={<CreateRoom />} />*/}
             {/*<Route path="/room/:roomCode" element={<Room />} />*/}
            
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