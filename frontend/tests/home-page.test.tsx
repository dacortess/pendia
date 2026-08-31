import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import React from "react";
import HomePage from "@/app/page";
import { AuthProvider } from "@/lib/auth-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

const mockReplace = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

afterEach(() => {
  mockReplace.mockClear();
});

function renderHome() {
  return render(
    <AuthProvider>
      <HomePage />
    </AuthProvider>
  );
}

describe("HomePage", () => {
  it("redirects to /login when unauthenticated", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    renderHome();

    await vi.waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("redirects to /dashboard when authenticated", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return HttpResponse.json({
          access_token: "restored-token",
          token_type: "bearer",
        });
      }),
      http.get(`${API_BASE}/users/me`, () => {
        return HttpResponse.json({
          id: 1,
          email: "test@example.com",
          full_name: "Test User",
          phone_number: null,
          whatsapp_opt_in: false,
          created_at: "2026-01-01T00:00:00Z",
        });
      })
    );

    renderHome();

    await vi.waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/dashboard");
    });
  });

  it("shows loading state during idle/loading", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        return HttpResponse.json({
          access_token: "token",
          token_type: "bearer",
        });
      })
    );

    renderHome();

    expect(screen.getByText("Cargando...")).toBeDefined();
  });

  it("does not redirect while status is loading", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, async () => {
        await new Promise((resolve) => setTimeout(resolve, 10000));
        return HttpResponse.json({
          access_token: "token",
          token_type: "bearer",
        });
      })
    );

    renderHome();

    await vi.waitFor(() => {
      expect(mockReplace).not.toHaveBeenCalled();
    });

    expect(screen.getByText("Cargando...")).toBeDefined();
  });
});
