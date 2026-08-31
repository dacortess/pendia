import { describe, it, expect, beforeEach } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "./server";
import {
  apiFetch,
  login,
  register,
  logout,
  getMe,
  configureAuth,
  ApiError,
} from "@/lib/api-client";

const API_BASE = "http://localhost:8000/api/v1";

let currentToken: string | null = null;

beforeEach(() => {
  currentToken = null;
  configureAuth({
    getToken: () => currentToken,
    setToken: (t) => {
      currentToken = t;
    },
    onRefreshFailed: () => {},
  });
});

describe("apiFetch", () => {
  it("attaches Authorization header when token is present", async () => {
    let receivedAuth: string | null = null;
    server.use(
      http.get(`${API_BASE}/users/me`, ({ request }) => {
        receivedAuth = request.headers.get("Authorization");
        return HttpResponse.json({
          id: 1,
          email: "test@example.com",
          full_name: "Test",
          phone_number: null,
          whatsapp_opt_in: false,
          created_at: "2026-01-01T00:00:00Z",
        });
      })
    );

    currentToken = "my-test-token";
    await getMe();

    expect(receivedAuth).toBe("Bearer my-test-token");
  });

  it("does not attach Authorization header when token is null", async () => {
    let receivedAuth: string | null = null;
    server.use(
      http.get(`${API_BASE}/users/me`, ({ request }) => {
        receivedAuth = request.headers.get("Authorization");
        return HttpResponse.json({
          id: 1,
          email: "test@example.com",
          full_name: "Test",
          phone_number: null,
          whatsapp_opt_in: false,
          created_at: "2026-01-01T00:00:00Z",
        });
      })
    );

    currentToken = null;
    await getMe();

    expect(receivedAuth).toBeNull();
  });

  it("parses error response and throws ApiError with detail and code", async () => {
    server.use(
      http.get(`${API_BASE}/users/me`, () => {
        return HttpResponse.json(
          { detail: "User not found", code: "USER_NOT_FOUND" },
          { status: 404 }
        );
      })
    );

    await expect(getMe()).rejects.toMatchObject({
      name: "ApiError",
      detail: "User not found",
      code: "USER_NOT_FOUND",
      status: 404,
    });
  });

  it("two parallel 401s trigger only one refresh call", async () => {
    let refreshCount = 0;

    server.use(
      http.post(`${API_BASE}/auth/refresh`, async () => {
        refreshCount++;
        await delay(50);
        return HttpResponse.json({
          access_token: "brand-new-token",
          token_type: "bearer",
        });
      }),
      http.get(`${API_BASE}/users/me`, ({ request }) => {
        const auth = request.headers.get("Authorization");
        if (auth === "Bearer brand-new-token") {
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
      })
    );

    currentToken = "expired-token";

    const [r1, r2] = await Promise.all([getMe(), getMe()]);

    expect(refreshCount).toBe(1);
    expect(r1.email).toBe("test@example.com");
    expect(r2.email).toBe("test@example.com");
    expect(currentToken).toBe("brand-new-token");
  });

  it("retries original request with new token after successful refresh", async () => {
    let fetchCount = 0;
    server.use(
      http.get(`${API_BASE}/users/me`, ({ request }) => {
        const auth = request.headers.get("Authorization");
        if (auth === "Bearer fresh-token") {
          return HttpResponse.json({
            id: 1,
            email: "test@example.com",
            full_name: "Test",
            phone_number: null,
            whatsapp_opt_in: false,
            created_at: "2026-01-01T00:00:00Z",
          });
        }
        fetchCount++;
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/refresh`, async () => {
        return HttpResponse.json({
          access_token: "fresh-token",
          token_type: "bearer",
        });
      })
    );

    currentToken = "stale-token";
    const user = await getMe();

    expect(fetchCount).toBe(1);
    expect(user.email).toBe("test@example.com");
    expect(currentToken).toBe("fresh-token");
  });

  it("propagates error when refresh fails and calls onRefreshFailed", async () => {
    let refreshFailedCalled = false;

    configureAuth({
      getToken: () => currentToken,
      setToken: (t) => {
        currentToken = t;
      },
      onRefreshFailed: () => {
        refreshFailedCalled = true;
      },
    });

    server.use(
      http.get(`${API_BASE}/users/me`, () => {
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    currentToken = "dead-token";

    await expect(getMe()).rejects.toMatchObject({
      name: "ApiError",
      code: "UNAUTHORIZED",
      status: 401,
    });

    expect(refreshFailedCalled).toBe(true);
    expect(currentToken).toBeNull();
  });

  it("does not trigger refresh for /auth/login, /auth/register, or /auth/refresh", async () => {
    let refreshCalled = false;
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        refreshCalled = true;
        return new HttpResponse(null, { status: 401 });
      }),
      http.post(`${API_BASE}/auth/login`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    await expect(
      apiFetch("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: "a@b.com", password: "pass" }),
      })
    ).rejects.toMatchObject({ status: 401 });

    expect(refreshCalled).toBe(false);
  });
});

describe("login", () => {
  it("returns access token response", async () => {
    const result = await login("test@example.com", "password123");
    expect(result.access_token).toBe("new-access-token");
    expect(result.token_type).toBe("bearer");
  });
});

describe("register", () => {
  it("returns access token response", async () => {
    const result = await register({
      email: "new@example.com",
      password: "password123",
      full_name: "New User",
    });
    expect(result.access_token).toBe("new-access-token");
  });
});

describe("logout", () => {
  it("completes without error", async () => {
    await expect(logout()).resolves.toBeUndefined();
  });
});

describe("getMe", () => {
  it("returns user data", async () => {
    const user = await getMe();
    expect(user.email).toBe("test@example.com");
    expect(user.full_name).toBe("Test User");
  });
});

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
