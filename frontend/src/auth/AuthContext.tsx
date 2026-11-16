import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { authService } from "../services/api";
import type { SessionUser } from "../types";

interface AuthValue {
  user: SessionUser | null;
  /** `true` tant que l'état de session initial (cookie) n'est pas connu. */
  checking: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthValue | null>(null);

/**
 * L'identité vient de /api/auth/me (cookie HttpOnly). Les routes protégées de l'interface ne sont qu'un
 * confort d'affichage : l'autorisation réelle est appliquée par le backend sur chaque appel.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    authService.me(controller.signal).then(
      (u) => !controller.signal.aborted && setUser(u),
      () => undefined, // non connecté : état normal
    ).finally(() => !controller.signal.aborted && setChecking(false));
    return () => controller.abort();
  }, []);

  const login = useCallback(async (username: string, password: string) => setUser(await authService.login(username, password)), []);
  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, checking, login, logout }), [user, checking, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  return ctx;
}
