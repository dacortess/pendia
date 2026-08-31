import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import DashboardPage from "@/app/(app)/dashboard/page";
import { GroupProvider } from "@/lib/groups-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

afterEach(() => {
  localStorage.clear();
});

function renderDashboard() {
  return render(
    <GroupProvider>
      <DashboardPage />
    </GroupProvider>
  );
}

describe("DashboardPage", () => {
  it("shows create group form when user has 0 groups", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      })
    );

    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(
      screen.getByText("Crea tu primer grupo")
    ).toBeDefined();
    expect(screen.getByLabelText(/nombre del grupo/i)).toBeDefined();
    expect(
      screen.getByRole("button", { name: /crear grupo/i })
    ).toBeDefined();
  });

  it("shows welcome message when user has 1+ groups", async () => {
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

    renderDashboard();

    await waitFor(() => {
      expect(
        screen.getByText("Bienvenido a Familia García")
      ).toBeDefined();
    });

    expect(screen.getByText("owner")).toBeDefined();
  });

  it("shows inline error when create group fails", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      }),
      http.post(`${API_BASE}/groups`, () => {
        return HttpResponse.json(
          { detail: "Internal server error", code: "INTERNAL_ERROR" },
          { status: 500 }
        );
      })
    );

    const user = userEvent.setup();
    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.type(
      screen.getByLabelText(/nombre del grupo/i),
      "Familia Test"
    );
    await user.click(screen.getByRole("button", { name: /crear grupo/i }));

    expect(
      await screen.findByText("No se pudo crear el grupo. Intenta de nuevo.")
    ).toBeDefined();
  });

  it("group name input has maxLength of 200", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      })
    );

    renderDashboard();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(
      screen.getByLabelText(/nombre del grupo/i)
    ).toHaveAttribute("maxLength", "200");
  });
});
