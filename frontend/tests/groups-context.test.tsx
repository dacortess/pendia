import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import { GroupProvider, useGroups } from "@/lib/groups-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

const mockGroups = [
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
];

function TestConsumer() {
  const ctx = useGroups();
  return (
    <div>
      <span data-testid="loading">{String(ctx.loading)}</span>
      <span data-testid="group-count">{ctx.groups.length}</span>
      <span data-testid="current-id">{ctx.currentGroupId ?? "none"}</span>
      <span data-testid="current-name">{ctx.currentGroup?.name ?? "none"}</span>
      {ctx.error && <span data-testid="error">{ctx.error}</span>}
      <button onClick={() => ctx.setCurrentGroupId(2)}>switch</button>
      <button onClick={() => ctx.createGroup("Nuevo")}>create</button>
    </div>
  );
}

afterEach(() => {
  localStorage.clear();
});

describe("GroupProvider", () => {
  it("mounts with empty groups array", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      })
    );

    render(
      <GroupProvider>
        <TestConsumer />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("group-count").textContent).toBe("0");
    expect(screen.getByTestId("current-id").textContent).toBe("none");
  });

  it("loads groups from GET /groups on mount", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json(mockGroups);
      })
    );

    render(
      <GroupProvider>
        <TestConsumer />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("group-count").textContent).toBe("2");
    expect(screen.getByTestId("current-id").textContent).toBe("1");
    expect(screen.getByTestId("current-name").textContent).toBe(
      "Familia García"
    );
  });

  it("setCurrentGroupId updates currentGroup", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json(mockGroups);
      })
    );

    render(
      <GroupProvider>
        <TestConsumer />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    await userEvent.click(screen.getByText("switch"));

    expect(screen.getByTestId("current-id").textContent).toBe("2");
    expect(screen.getByTestId("current-name").textContent).toBe(
      "Familia López"
    );
    expect(localStorage.getItem("currentGroupId")).toBe("2");
  });

  it("createGroup calls POST /groups and appends group", async () => {
    let createCalled = false;

    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json(mockGroups);
      }),
      http.post(`${API_BASE}/groups`, async ({ request }) => {
        createCalled = true;
        const body = (await request.json()) as { name: string };
        return HttpResponse.json(
          {
            id: 3,
            name: body.name,
            created_by: 1,
            created_at: "2026-01-03T00:00:00Z",
            updated_at: "2026-01-03T00:00:00Z",
            my_role: "owner",
          },
          { status: 201 }
        );
      })
    );

    render(
      <GroupProvider>
        <TestConsumer />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });

    await userEvent.click(screen.getByText("create"));

    await waitFor(() => {
      expect(createCalled).toBe(true);
      expect(screen.getByTestId("group-count").textContent).toBe("3");
      expect(screen.getByTestId("current-id").textContent).toBe("3");
      expect(screen.getByTestId("current-name").textContent).toBe("Nuevo");
    });
    expect(localStorage.getItem("currentGroupId")).toBe("3");
  });

  it("invalid localStorage falls back to first group", async () => {
    localStorage.setItem("currentGroupId", "999");

    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json(mockGroups);
      })
    );

    render(
      <GroupProvider>
        <TestConsumer />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading").textContent).toBe("false");
    });
    expect(screen.getByTestId("current-id").textContent).toBe("1");
    expect(localStorage.getItem("currentGroupId")).toBe("1");
  });
});
