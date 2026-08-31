import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { renderHook, waitFor, act, cleanup } from "@testing-library/react";
import React from "react";
import { server } from "./server";
import { AuthProvider, useAuth } from "@/lib/auth-context";

const API_BASE = "http://localhost:8000/api/v1";

function createWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>;
  };
}

describe("AuthContext", () => {
  describe("logout", () => {
    it("clears state and calls POST /auth/logout", async () => {
      let logoutCalled = false;

      server.use(
        http.post(`${API_BASE}/auth/refresh`, () => {
          return HttpResponse.json({
            access_token: "logout-token",
            token_type: "bearer",
          });
        }),
        http.get(`${API_BASE}/users/me`, ({ request }) => {
          const auth = request.headers.get("Authorization");
          if (auth === "Bearer logout-token") {
            return HttpResponse.json({
              id: 1,
              email: "test@example.com",
              full_name: "Test",
              phone_number: null,
              whatsapp_opt_in: false,
              created_at: "2026-01-01T00:00:00Z",
            });
          }
          return new HttpResponse(null, { status: 401 });
        }),
        http.post(`${API_BASE}/auth/logout`, () => {
          logoutCalled = true;
          return new HttpResponse(null, { status: 204 });
        })
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.status).toBe("authenticated");
      });

      expect(result.current.user?.email).toBe("test@example.com");

      await act(async () => {
        await result.current.logout();
      });

      expect(logoutCalled).toBe(true);
      expect(result.current.status).toBe("unauthenticated");
      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
    });
  });

  describe("on mount without existing session (refresh fails)", () => {
    it("ends in unauthenticated status without throwing", async () => {
      server.use(
        http.post(`${API_BASE}/auth/refresh`, () => {
          return new HttpResponse(null, { status: 401 });
        })
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.status).toBe("unauthenticated");
      });

      expect(result.current.user).toBeNull();
      expect(result.current.accessToken).toBeNull();
    });
  });

  describe("on mount with existing session (refresh succeeds)", () => {
    it("restores session and fetches user", async () => {
      server.use(
        http.post(`${API_BASE}/auth/refresh`, () => {
          return HttpResponse.json({
            access_token: "restored-token",
            token_type: "bearer",
          });
        }),
        http.get(`${API_BASE}/users/me`, ({ request }) => {
          const auth = request.headers.get("Authorization");
          if (auth === "Bearer restored-token") {
            return HttpResponse.json({
              id: 1,
              email: "restored@example.com",
              full_name: "Restored User",
              phone_number: null,
              whatsapp_opt_in: false,
              created_at: "2026-01-01T00:00:00Z",
            });
          }
          return new HttpResponse(null, { status: 401 });
        })
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.status).toBe("authenticated");
      });

      expect(result.current.user?.email).toBe("restored@example.com");
      expect(result.current.accessToken).toBe("restored-token");
    });
  });

  describe("login", () => {
    it("successful login sets status to authenticated and fetches user", async () => {
      server.use(
        http.post(`${API_BASE}/auth/refresh`, () => {
          return new HttpResponse(null, { status: 401 });
        })
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.status).toBe("unauthenticated");
      });

      await act(async () => {
        await result.current.login("test@example.com", "password123");
      });

      expect(result.current.status).toBe("authenticated");
      expect(result.current.user?.email).toBe("test@example.com");
      expect(result.current.accessToken).toBe("new-access-token");
    });

    it("failed login sets status to unauthenticated and re-throws error", async () => {
      server.use(
        http.post(`${API_BASE}/auth/refresh`, () => {
          return new HttpResponse(null, { status: 401 });
        }),
        http.post(`${API_BASE}/auth/login`, () => {
          return HttpResponse.json(
            { detail: "Invalid credentials", code: "INVALID_CREDENTIALS" },
            { status: 401 }
          );
        })
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useAuth(), { wrapper });

      await waitFor(() => {
        expect(result.current.status).toBe("unauthenticated");
      });

      await expect(
        act(async () => {
          await result.current.login("bad@example.com", "wrongpass");
        })
      ).rejects.toMatchObject({
        detail: "Invalid credentials",
        code: "INVALID_CREDENTIALS",
      });

      expect(result.current.status).toBe("unauthenticated");
      expect(result.current.user).toBeNull();
    });
  });
});
