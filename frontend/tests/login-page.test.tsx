import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import LoginPage from "@/app/(auth)/login/page";
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

vi.mock("next/link", () => {
  return {
    default: ({
      children,
      href,
    }: {
      children: React.ReactNode;
      href: string;
    }) => <a href={href}>{children}</a>,
  };
});

afterEach(() => {
  mockReplace.mockClear();
});

function renderLogin() {
  return render(
    <AuthProvider>
      <LoginPage />
    </AuthProvider>
  );
}

describe("LoginPage", () => {
  it("renders the login form with email and password fields", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    expect(screen.getByLabelText(/email/i)).toBeDefined();
    expect(screen.getByLabelText(/contraseña/i)).toBeDefined();
    expect(
      screen.getByRole("button", { name: /iniciar sesión/i })
    ).toBeDefined();
  });

  it("successful login navigates to /", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    const user = userEvent.setup();
    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "password123");

    server.use(
      http.post(`${API_BASE}/auth/login`, async () => {
        return HttpResponse.json({
          access_token: "new-access-token",
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

    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await vi.waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/");
    });
  });

  it("shows error message on INVALID_CREDENTIALS", async () => {
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

    const user = userEvent.setup();
    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "wrongpass");

    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText("Email o contraseña incorrectos.")
    ).toBeDefined();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows generic error on unknown error", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/login`, () => {
        return HttpResponse.json(
          { detail: "Something went wrong", code: "UNKNOWN_ERROR" },
          { status: 500 }
        );
      })
    );

    const user = userEvent.setup();
    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    expect(
      await screen.findByText(
        "No se pudo iniciar sesión. Intenta de nuevo."
      )
    ).toBeDefined();
  });

  it("disables submit button while request is pending", async () => {
    let resolveLogin: (value: unknown) => void;
    const loginPromise = new Promise((resolve) => {
      resolveLogin = resolve;
    });

    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/login`, async () => {
        await loginPromise;
        return HttpResponse.json({
          access_token: "new-access-token",
          token_type: "bearer",
        });
      })
    );

    const user = userEvent.setup();
    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /iniciar sesión/i }));

    await vi.waitFor(() => {
      const button = screen.getByRole("button", { name: /conectando/i });
      expect(button).toBeDisabled();
    });

    resolveLogin!(null);
  });

  it("renders link to register page", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    renderLogin();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    const link = screen.getByRole("link", { name: /regístrate/i });
    expect(link.getAttribute("href")).toBe("/register");
  });
});
