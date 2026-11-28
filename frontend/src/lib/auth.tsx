import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, tokenStore } from "./api";
import type { User } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, guard?: (u: User) => string | null) => Promise<void>;
  register: (payload: Record<string, unknown> & { email: string; password: string }) => Promise<void>;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!tokenStore.get());

  const clearSession = useCallback(() => { tokenStore.clear(); setUser(null); }, []);
  const logout = useCallback(async () => {                // revoke the token on the server, then forget it locally (always)
    try { await api("/auth/logout", { method: "POST" }); } catch { /* already expired or offline: still sign out here */ }
    clearSession();
  }, [clearSession]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    api<User>("/auth/me").then(setUser).catch(() => tokenStore.clear()).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    window.addEventListener("dermai:logout", clearSession);
    return () => window.removeEventListener("dermai:logout", clearSession);
  }, [clearSession]);

  const login = useCallback(async (email: string, password: string, guard?: (u: User) => string | null) => {
    const form = new URLSearchParams({ username: email, password });
    const res = await api<{ access_token: string; user: User }>("/auth/login", { form });
    const problem = guard?.(res.user);
    if (problem) throw new ApiError(403, problem);   // nothing stored, no session started
    tokenStore.set(res.access_token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (payload: Record<string, unknown> & { email: string; password: string }) => {
    await api("/auth/register", { json: payload });
    await login(payload.email, payload.password);
  }, [login]);

  const refresh = useCallback(async () => { setUser(await api<User>("/auth/me")); }, []);

  const value = useMemo(() => ({ user, loading, login, register, refresh, logout }), [user, loading, login, register, refresh, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used inside AuthProvider");
  return c;
}

