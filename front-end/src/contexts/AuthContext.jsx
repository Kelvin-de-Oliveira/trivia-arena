import { useCallback, useEffect, useMemo, useState } from 'react';
import { setAuthToken, setOnSessionExpired } from '../api/client';
import { AuthContext } from './auth-context';

const DEFAULT_GUEST_NAME = 'Visitante';

const normalizePlayerName = (name, fallback = DEFAULT_GUEST_NAME) => {
  const trimmed = name?.trim();
  return trimmed || fallback;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [sessionExpired, setSessionExpired] = useState(false);

  const login = useCallback((jwt, user_id, name) => {
    setAuthToken(jwt);
    setSessionExpired(false);
    setUser({
      playerId: user_id,
      name: normalizePlayerName(name, 'Jogador'),
      jwt,
      isAnonymous: false,
    });
  }, []);

  const logout = useCallback(() => {
    setAuthToken(null);
    setSessionExpired(false);
    setUser(null);
  }, []);

  const joinAsAnonymous = useCallback((name) => {
    const anonId = user?.isAnonymous && user.playerId
      ? user.playerId
      : `anon:${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`;
    const anonymousUser = {
      playerId: anonId,
      name: normalizePlayerName(name, user?.isAnonymous ? user.name : DEFAULT_GUEST_NAME),
      jwt: null,
      isAnonymous: true,
    };

    setAuthToken(null);
    setSessionExpired(false);
    setUser(anonymousUser);

    return anonymousUser;
  }, [user]);

  const updateName = useCallback((newName) => {
    setUser((prev) => (prev ? { ...prev, name: normalizePlayerName(newName, prev.name) } : prev));
  }, []);

  useEffect(() => {
    setOnSessionExpired(() => {
      setSessionExpired(true);
      setAuthToken(null);
      setUser(null);
    });
    return () => setOnSessionExpired(null);
  }, []);

  const value = useMemo(() => ({
    user,
    login,
    logout,
    joinAsAnonymous,
    sessionExpired,
    updateName,
  }), [user, login, logout, joinAsAnonymous, sessionExpired, updateName]);

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
