import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import ObligationDetailPage from "@/app/(app)/obligations/detail/page";
import { GroupProvider } from "@/lib/groups-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

const mockPush = vi.hoisted(() => vi.fn());
const mockSearchParams = vi.hoisted(() => new URLSearchParams({ id: "1" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

const mockGroup = {
  id: 1,
  name: "Familia García",
  created_by: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  my_role: "owner",
};

const mockMemberGroup = {
  ...mockGroup,
  my_role: "member",
};

const mockAdminGroup = {
  ...mockGroup,
  my_role: "admin",
};

const mockObligation = {
  id: 1,
  group_id: 1,
  category_id: null,
  payment_method_id: null,
  responsible_user_id: null,
  name: "Internet mensual",
  provider_name: "Claro",
  external_reference: null,
  notes: "Pago mensual de internet",
  currency: "COP" as const,
  expected_amount_cents: 89900,
  is_variable_amount: false,
  is_subscription: true,
  auto_debit: true,
  is_essential: true,
  periodicity: "MONTHLY" as const,
  due_day: 15,
  due_month: null,
  start_date: "2026-01-01",
  end_date: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function renderDetail(group = mockGroup) {
  return render(
    <GroupProvider
      initialState={{
        groups: [group],
        currentGroupId: group.id,
        loading: false,
      }}
    >
      <ObligationDetailPage />
    </GroupProvider>
  );
}

afterEach(() => {
  localStorage.clear();
  mockPush.mockClear();
  mockSearchParams.set("id", "1");
  server.resetHandlers();
});

describe("ObligationDetailPage", () => {
  it("shows obligation data when loaded successfully", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("Internet mensual")).toBeDefined();
    expect(screen.getByText("Claro")).toBeDefined();
    expect(screen.getByText(/\$899/)).toBeDefined();
    expect(screen.getByText("Mensual")).toBeDefined();
    expect(screen.getByText("Día 15 de cada mes")).toBeDefined();
    expect(screen.getByText("Pago mensual de internet")).toBeDefined();
    expect(screen.getByText("Variable: No")).toBeDefined();
    expect(screen.getByText("Suscripción: Sí")).toBeDefined();
    expect(screen.getByText("Débito automático: Sí")).toBeDefined();
    expect(screen.getByText("Esencial: Sí")).toBeDefined();
  });

  it("shows 'Obligación no encontrada.' on 404", async () => {
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("Obligación no encontrada.")).toBeDefined();
    expect(
      screen.getByRole("link", { name: /volver a obligaciones/i })
    ).toHaveAttribute("href", "/obligations");
  });

  it("does not show edit/delete buttons when role is member", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    renderDetail(mockMemberGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.queryByText("Editar")).toBeNull();
    expect(screen.queryByText("Eliminar")).toBeNull();
  });

  it("shows edit/delete buttons when role is owner", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    renderDetail(mockGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("Editar")).toBeDefined();
    expect(screen.getByText("Eliminar")).toBeDefined();
  });

  it("shows edit/delete buttons when role is admin", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    renderDetail(mockAdminGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("Editar")).toBeDefined();
    expect(screen.getByText("Eliminar")).toBeDefined();
  });

  it("edit: shows form pre-filled and saves changes", async () => {
    let patchCalled = false;
    let patchBody: Record<string, unknown> = {};

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      }),
      http.patch(`${API_BASE}/groups/:groupId/obligations/:id`, async ({ request }) => {
        patchCalled = true;
        patchBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          ...mockObligation,
          name: "Internet actualizado",
          provider_name: "Movistar",
        });
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Editar"));

    const nameInput = screen.getByLabelText(/^nombre/i);
    expect(nameInput).toHaveValue("Internet mensual");

    const proveedorInput = screen.getByLabelText(/proveedor/i);
    expect(proveedorInput).toHaveValue("Claro");

    await user.clear(nameInput);
    await user.type(nameInput, "Internet actualizado");
    await user.clear(proveedorInput);
    await user.type(proveedorInput, "Movistar");

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    await waitFor(() => {
      expect(patchCalled).toBe(true);
      expect(patchBody.name).toBe("Internet actualizado");
      expect(patchBody.provider_name).toBe("Movistar");
      expect(screen.getByText("Internet actualizado")).toBeDefined();
      expect(screen.getByText("Movistar")).toBeDefined();
    });
  });

  it("edit: validates annual due_month required", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Editar"));

    await user.selectOptions(
      screen.getByLabelText(/periodicidad/i),
      "ANNUAL"
    );

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(
      screen.getByText("El mes es obligatorio para periodicidad anual.")
    ).toBeDefined();
  });

  it("edit: shows FORBIDDEN_NOT_ADMIN error", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      }),
      http.patch(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(
          { detail: "Forbidden", code: "FORBIDDEN_NOT_ADMIN" },
          { status: 403 }
        );
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Editar"));

    await user.click(screen.getByRole("button", { name: /guardar cambios/i }));

    expect(
      await screen.findByText(
        "No tienes permisos para editar obligaciones."
      )
    ).toBeDefined();
  });

  it("delete: shows confirmation, cancel hides it", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Eliminar"));

    expect(
      screen.getByText(
        /¿Eliminar esta obligación\? No podrás deshacer esta acción/i
      )
    ).toBeDefined();
    expect(screen.getByText("Confirmar")).toBeDefined();
    expect(screen.getByText("Cancelar")).toBeDefined();

    await user.click(screen.getByText("Cancelar"));

    expect(
      screen.queryByText(
        /¿Eliminar esta obligación\? No podrás deshacer esta acción/i
      )
    ).toBeNull();
  });

  it("delete: confirm calls DELETE and redirects", async () => {
    let deleteCalled = false;

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      }),
      http.delete(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        deleteCalled = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Eliminar"));

    await user.click(screen.getByText("Confirmar"));

    await waitFor(() => {
      expect(deleteCalled).toBe(true);
      expect(mockPush).toHaveBeenCalledWith("/obligations");
    });
  });

  it("delete: FORBIDDEN_NOT_ADMIN shows error without redirecting", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(mockObligation);
      }),
      http.delete(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(
          { detail: "Forbidden", code: "FORBIDDEN_NOT_ADMIN" },
          { status: 403 }
        );
      })
    );

    const user = userEvent.setup();
    renderDetail();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("Eliminar"));

    await user.click(screen.getByText("Confirmar"));

    expect(
      await screen.findByText(
        "No tienes permisos para eliminar obligaciones."
      )
    ).toBeDefined();
    expect(mockPush).not.toHaveBeenCalled();
  });

  it("shows generic error when load fails", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
        return HttpResponse.json(
          { detail: "Server error" },
          { status: 500 }
        );
      })
    );

    renderDetail();

    await waitFor(() => {
      expect(
        screen.getByText("No se pudo cargar la obligación.")
      ).toBeDefined();
    });
  });
});
