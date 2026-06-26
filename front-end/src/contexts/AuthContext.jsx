import React, { createContext, useState, useContext, useCallback } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);

  const login = useCallback((jwt, user_id, name) => {
    setUser({
      playerId: user_id,
      name: name,
      jwt: jwt,
      isAnonymous: false,
    });
  }, []);

  const logout = useCallback(() => {
    setUser(null);
  }, []);

  const joinAsAnonymous = useCallback(() => {
    const anonId = `anon:${crypto.randomUUID()}`;
    
    setUser({
      playerId: anonId,
      name: 'Jogador Anônimo', 
      jwt: null, 
      isAnonymous: true,
    });

    return anonId;
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, joinAsAnonymous }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser usado dentro de um AuthProvider");
  }
  return context;
};