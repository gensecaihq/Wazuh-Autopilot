import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, getToken, setToken, setUnauthorizedHandler } from "@/api/client";
import { useMe } from "@/api/hooks";
import type { LoginResponse, User } from "@/api/types";

interface AuthCtx {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => void;
  can: (perm: string | string[] | undefined) => boolean;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [token, setTok] = useState<string | null>(() => getToken());
  const me = useMe(!!token);

  const logout = useCallback(() => {
    setToken(null);
    setTok(null);
    qc.clear();
  }, [qc]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setTok(null);
      qc.clear();
    });
  }, [qc]);

  const login = useCallback(
    async (email: string, password: string) => {
      const res = await api.public.post<LoginResponse>("/auth/login", { email, password });
      setToken(res.access_token);
      setTok(res.access_token);
      qc.setQueryData(["me"], res.user);
      return res.user;
    },
    [qc],
  );

  const user = token ? (me.data ?? null) : null;
  const can = useCallback(
    (perm: string | string[] | undefined) => {
      if (!perm) return true;
      if (!user) return false;
      const perms = new Set(user.permissions);
      if (perms.has("*") || user.role === "admin") return true;
      return (Array.isArray(perm) ? perm : [perm]).some((p) => perms.has(p));
    },
    [user],
  );

  const value = useMemo(
    () => ({ user, token, loading: !!token && me.isLoading, login, logout, can }),
    [user, token, me.isLoading, login, logout, can],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("AuthProvider missing");
  return c;
}
