import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, setCsrfToken } from "./api";
import type { Auth } from "./types";

interface AuthCtx {
  user: Auth | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Auth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Restore session on load (cookie may still be valid after a refresh).
    api
      .me()
      .then((u) => {
        setCsrfToken(u.csrf_token);
        setUser(u);
      })
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const u = await api.login(email, password);
    setCsrfToken(u.csrf_token);
    setUser(u);
  };

  const logout = async () => {
    try {
      await api.logout();
    } finally {
      setCsrfToken("");
      setUser(null);
    }
  };

  const refreshUser = async () => {
    const u = await api.me();
    setCsrfToken(u.csrf_token);
    setUser(u);
  };

  return (
    <Ctx.Provider value={{ user, loading, login, logout, refreshUser }}>{children}</Ctx.Provider>
  );
}

export const useAuth = () => useContext(Ctx);
