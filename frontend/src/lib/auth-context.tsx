"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import {
  configureAuth as configureApiClient,
  login as apiLogin,
  register as apiRegister,
  logout as apiLogout,
  getMe,
  refreshToken as apiRefreshToken,
} from "./api-client";

interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  phone_number: string | null;
  whatsapp_opt_in: boolean;
  created_at: string;
}

type AuthStatus = "idle" | "loading" | "authenticated" | "unauthenticated";

interface AuthState {
  status: AuthStatus;
  user: UserResponse | null;
  accessToken: string | null;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (data: {
    email: string;
    password: string;
    full_name: string;
    phone_number?: string;
    invite_code?: string;
  }) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    status: "idle",
    user: null,
    accessToken: null,
  });

  const accessTokenRef = useRef<string | null>(null);
  accessTokenRef.current = state.accessToken;

  const setToken = useCallback((token: string | null) => {
    setState((prev) => ({ ...prev, accessToken: token }));
  }, []);

  const onRefreshFailed = useCallback(() => {
    setState({ status: "unauthenticated", user: null, accessToken: null });
  }, []);

  useEffect(() => {
    configureApiClient({
      getToken: () => accessTokenRef.current,
      setToken,
      onRefreshFailed,
    });
  }, [setToken, onRefreshFailed]);

  useEffect(() => {
    let cancelled = false;

    async function tryRefresh() {
      setState((prev) => ({ ...prev, status: "loading" }));
      try {
        const response = await apiRefreshToken();
        if (cancelled) return;
        setState((prev) => ({
          ...prev,
          accessToken: response.access_token,
          status: "loading",
        }));
        const user = await getMe();
        if (cancelled) return;
        setState({ status: "authenticated", user, accessToken: response.access_token });
      } catch {
        if (cancelled) return;
        setState({ status: "unauthenticated", user: null, accessToken: null });
      }
    }

    tryRefresh();

    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      setState((prev) => ({ ...prev, status: "loading" }));
      try {
        const response = await apiLogin(email, password);
        setState((prev) => ({
          ...prev,
          accessToken: response.access_token,
          status: "loading",
        }));
        const user = await getMe();
        setState({ status: "authenticated", user, accessToken: response.access_token });
      } catch (err) {
        setState({ status: "unauthenticated", user: null, accessToken: null });
        throw err;
      }
    },
    []
  );

  const register = useCallback(
    async (data: {
      email: string;
      password: string;
      full_name: string;
      phone_number?: string;
      invite_code?: string;
    }) => {
      setState((prev) => ({ ...prev, status: "loading" }));
      try {
        const response = await apiRegister(data);
        setState((prev) => ({
          ...prev,
          accessToken: response.access_token,
          status: "loading",
        }));
        const user = await getMe();
        setState({ status: "authenticated", user, accessToken: response.access_token });
      } catch (err) {
        setState({ status: "unauthenticated", user: null, accessToken: null });
        throw err;
      }
    },
    []
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Logout is idempotent — clear state even if API call fails
    }
    setState({ status: "unauthenticated", user: null, accessToken: null });
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
