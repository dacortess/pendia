import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import React from "react";
import AppLayout from "@/app/(app)/layout";
import { AuthProvider } from "@/lib/auth-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

const mockReplace = vi.hoisted(() => vi.fn());
const mockPathname = vi.hoisted(() => ({ value: "/dashboard" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: mockReplace,
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  usePathname: () => mockPathname.value,
}));

afterEach(() => {
  mockReplace.mockClear();
  mockPathname.value = "/dashboard";
});

describe("AppLayout", () => {
  it("redirects to /login when unauthenticated", async () => {
    server.use(
      http.post(`${API_BASE}/auth/refresh`, () => {
        return new HttpResponse(null, { status: 401 });
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith("/login");
    });
  });

  it("shows group name as text (NO select) when user has 1 group", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([
          {
            id: 1,
            name: "Familia García",
            created_by: 1,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            my_role: "owner",
          },
        ]);
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Familia García")).toBeDefined();
    });

    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("shows select dropdown when user has 2+ groups", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([
          {
            id: 1,
            name: "Familia García",
            created_by: 1,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            my_role: "owner",
          },
          {
            id: 2,
            name: "Familia López",
            created_by: 2,
            created_at: "2026-01-02T00:00:00Z",
            updated_at: "2026-01-02T00:00:00Z",
            my_role: "member",
          },
        ]);
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByRole("combobox")).toBeDefined();
    });

    expect(screen.getByDisplayValue("Familia García")).toBeDefined();
  });

  it("has sidebar with Dashboard and Obligaciones links", async () => {
    mockPathname.value = "/dashboard";

    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([
          {
            id: 1,
            name: "Familia García",
            created_by: 1,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            my_role: "owner",
          },
        ]);
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Familia García")).toBeDefined();
    });

    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    const obligationsLink = screen.getByRole("link", { name: /obligaciones/i });

    expect(dashboardLink).toHaveAttribute("href", "/dashboard");
    expect(obligationsLink).toHaveAttribute("href", "/obligations");

    expect(dashboardLink.className).toMatch(/bg-blue-50/);
    expect(obligationsLink.className).not.toMatch(/bg-blue-50/);
  });

  it("highlights Obligaciones link when on /obligations", async () => {
    mockPathname.value = "/obligations";

    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([
          {
            id: 1,
            name: "Familia García",
            created_by: 1,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            my_role: "owner",
          },
        ]);
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Familia García")).toBeDefined();
    });

    const dashboardLink = screen.getByRole("link", { name: /dashboard/i });
    const obligationsLink = screen.getByRole("link", { name: /obligaciones/i });

    expect(dashboardLink.className).not.toMatch(/bg-blue-50/);
    expect(obligationsLink.className).toMatch(/bg-blue-50/);
  });

  it("has Pagos link in sidebar with href /payments", async () => {
    mockPathname.value = "/dashboard";

    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([
          {
            id: 1,
            name: "Familia García",
            created_by: 1,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            my_role: "owner",
          },
        ]);
      })
    );

    render(
      <AuthProvider>
        <AppLayout>
          <div>child</div>
        </AppLayout>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(screen.getByText("Familia García")).toBeDefined();
    });

    const pagosLink = screen.getByRole("link", { name: /pagos/i });
    expect(pagosLink).toHaveAttribute("href", "/payments");
  });
});
