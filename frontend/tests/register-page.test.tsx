import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import RegisterPage from "@/app/(auth)/register/page";
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

function renderRegister() {
  return render(
    <AuthProvider>
      <RegisterPage />
    </AuthProvider>
  );
}

describe("RegisterPage", () => {
  it("renders the register form with all fields", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    expect(screen.getByLabelText(/nombre completo/i)).toBeDefined();
    expect(screen.getByLabelText(/email/i)).toBeDefined();
    expect(screen.getByLabelText(/^contraseña/i)).toBeDefined();
    expect(screen.getByLabelText(/teléfono/i)).toBeDefined();
    expect(screen.getByLabelText(/código de invitación/i)).toBeDefined();
    expect(
      screen.getByRole("button", { name: /crear cuenta/i })
    ).toBeDefined();
  });

  it("successful register navigates to /", async () => {
    let registerCalled = false;

    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/register`, async () => {
        registerCalled = true;
        return HttpResponse.json(
          { access_token: "new-access-token", token_type: "bearer" },
          { status: 201 }
        );
      }),
      http.get(`${API_BASE}/users/me`, () => {
        return HttpResponse.json({
          id: 1,
          email: "new@example.com",
          full_name: "New User",
          phone_number: null,
          whatsapp_opt_in: false,
          created_at: "2026-01-01T00:00:00Z",
        });
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "New User");
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    await vi.waitFor(() => {
      expect(registerCalled).toBe(true);
      expect(mockReplace).toHaveBeenCalledWith("/");
    });
  });

  it("shows error on EMAIL_ALREADY_EXISTS", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/register`, () => {
        return HttpResponse.json(
          { detail: "Email already registered", code: "EMAIL_ALREADY_EXISTS" },
          { status: 409 }
        );
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "Test User");
    await user.type(screen.getByLabelText(/email/i), "taken@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText("Ya existe una cuenta con ese email.")
    ).toBeDefined();
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("shows error on INVALID_INVITE_CODE", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/register`, () => {
        return HttpResponse.json(
          {
            detail: "Invalid invite code",
            code: "INVALID_INVITE_CODE",
          },
          { status: 404 }
        );
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "Test User");
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");
    await user.type(screen.getByLabelText(/código de invitación/i), "BADCODE");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText(
        "El código de invitación no es válido o expiró."
      )
    ).toBeDefined();
  });

  it("shows error on ALREADY_MEMBER", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/register`, () => {
        return HttpResponse.json(
          { detail: "Already a member", code: "ALREADY_MEMBER" },
          { status: 409 }
        );
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "Test User");
    await user.type(screen.getByLabelText(/email/i), "new@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");
    await user.type(
      screen.getByLabelText(/código de invitación/i),
      "EXISTING"
    );

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText("Ya eres miembro de ese grupo.")
    ).toBeDefined();
  });

  it("short password shows client-side error and never fires API request", async () => {
    let registerCount = 0;

    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/register`, async () => {
        registerCount++;
        return HttpResponse.json(
          { access_token: "new-access-token", token_type: "bearer" },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "Test User");
    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "short");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText(
        "La contraseña debe tener al menos 8 caracteres."
      )
    ).toBeDefined();
    expect(registerCount).toBe(0);
  });

  it("shows error for invalid email format", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/nombre completo/i), "Test User");
    await user.type(screen.getByLabelText(/email/i), "not-an-email");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText("Ingresa un email válido.")
    ).toBeDefined();
  });

  it("shows error for empty full name", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    const user = userEvent.setup();
    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    await user.type(screen.getByLabelText(/email/i), "test@example.com");
    await user.type(screen.getByLabelText(/^contraseña/i), "password123");

    await user.click(screen.getByRole("button", { name: /crear cuenta/i }));

    expect(
      await screen.findByText("El nombre es obligatorio.")
    ).toBeDefined();
  });

  it("renders link to login page", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    renderRegister();

    await waitFor(() => {
      expect(screen.queryByText(/conectando/i)).toBeNull();
    });

    const link = screen.getByRole("link", { name: /inicia sesión/i });
    expect(link.getAttribute("href")).toBe("/login");
  });
});
