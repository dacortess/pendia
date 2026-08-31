import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import ObligationsPage from "@/app/(app)/obligations/page";
import { GroupProvider } from "@/lib/groups-context";
import { server } from "./server";

const API_BASE = "http://localhost:8000/api/v1";

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
  notes: null,
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

const mockAnnualObligation = {
  ...mockObligation,
  id: 2,
  name: "Seguro anual",
  periodicity: "ANNUAL" as const,
  due_month: 3,
  provider_name: null,
  is_essential: false,
};

afterEach(() => {
  localStorage.clear();
});

function renderPage(group = mockGroup) {
  return render(
    <GroupProvider
      initialState={{
        groups: [group],
        currentGroupId: group.id,
        loading: false,
      }}
    >
      <ObligationsPage />
    </GroupProvider>
  );
}

describe("ObligationsPage", () => {
  it("shows empty state when no obligations exist", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(
      screen.getByText("Aún no tienes obligaciones registradas.")
    ).toBeDefined();
  });

  it("renders table with obligation data", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([mockObligation]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    expect(screen.getByText("Claro")).toBeDefined();
    expect(screen.getByText("$899")).toBeDefined();
    expect(screen.getByText("Mensual")).toBeDefined();
    expect(screen.getByText("Día 15 de cada mes")).toBeDefined();
    expect(screen.getByText("Sí")).toBeDefined();
  });

  it("hides create button when role is member", async () => {
    renderPage(mockMemberGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.queryByText("+ Nueva obligación")).toBeNull();
  });

  it("shows create button when role is owner", async () => {
    renderPage(mockGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("+ Nueva obligación")).toBeDefined();
  });

  it("shows create button when role is admin", async () => {
    renderPage(mockAdminGroup);

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    expect(screen.getByText("+ Nueva obligación")).toBeDefined();
  });

  it("creates obligation and updates table", async () => {
    let postCalled = false;

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
        postCalled = true;
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 2,
            group_id: 1,
            category_id: null,
            payment_method_id: null,
            responsible_user_id: null,
            name: body.name,
            provider_name: body.provider_name ?? null,
            external_reference: null,
            notes: body.notes ?? null,
            currency: body.currency ?? "COP",
            expected_amount_cents: body.expected_amount_cents ?? 0,
            is_variable_amount: body.is_variable_amount ?? false,
            is_subscription: body.is_subscription ?? false,
            auto_debit: body.auto_debit ?? false,
            is_essential: body.is_essential ?? true,
            periodicity: body.periodicity ?? "MONTHLY",
            due_day: body.due_day ?? 1,
            due_month: body.due_month ?? null,
            start_date: body.start_date ?? "2026-01-01",
            end_date: body.end_date ?? null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Netflix");
    await user.type(screen.getByLabelText(/monto esperado/i), "15.900");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    await waitFor(() => {
      expect(postCalled).toBe(true);
      expect(screen.getByText("Netflix")).toBeDefined();
      expect(screen.queryByText("+ Nueva obligación")).toBeDefined();
    });
  });

  it("shows annual month field only when periodicity is annual", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([mockAnnualObligation]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Seguro anual")).toBeDefined();
    });

    expect(screen.getByText("15/3 de cada año")).toBeDefined();
  });

  it("validates annual due_month required", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Seguro");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.selectOptions(screen.getByLabelText(/periodicidad/i), "ANNUAL");

    expect(screen.getByLabelText(/mes de vencimiento/i)).toBeDefined();

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    expect(
      screen.getByText("El mes es obligatorio para periodicidad anual.")
    ).toBeDefined();
  });

  it("hides month field when periodicity is not annual", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    expect(screen.queryByLabelText(/mes de vencimiento/i)).toBeNull();

    await user.selectOptions(screen.getByLabelText(/periodicidad/i), "ANNUAL");

    expect(screen.getByLabelText(/mes de vencimiento/i)).toBeDefined();

    await user.selectOptions(screen.getByLabelText(/periodicidad/i), "MONTHLY");

    expect(screen.queryByLabelText(/mes de vencimiento/i)).toBeNull();
  });

  it("shows FORBIDDEN_NOT_ADMIN error message", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json(
          { detail: "Forbidden", code: "FORBIDDEN_NOT_ADMIN" },
          { status: 403 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Test");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    expect(
      await screen.findByText("No tienes permisos para crear obligaciones.")
    ).toBeDefined();
  });

  it("shows generic error for unexpected 500", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json(
          { detail: "Internal server error", code: "INTERNAL_ERROR" },
          { status: 500 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Test");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    expect(
      await screen.findByText(
        "No se pudo crear la obligación. Intenta de nuevo."
      )
    ).toBeDefined();
  });

  it("shows message to create group when no currentGroup", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      })
    );

    render(
      <GroupProvider
        initialState={{
          groups: [],
          currentGroupId: null,
          loading: false,
        }}
      >
        <ObligationsPage />
      </GroupProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(/primero creá un grupo desde el dashboard/i)
      ).toBeDefined();
    });

    expect(screen.getByRole("link", { name: /ir al dashboard/i })).toHaveAttribute(
      "href",
      "/dashboard"
    );
  });

  it("renders obligation name as link to detail page", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([mockObligation]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    const link = screen.getByRole("link", { name: "Internet mensual" });
    expect(link).toHaveAttribute("href", "/obligations/detail?id=1");
  });

  it("shows load error when listObligations fails", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json(
          { detail: "Server error" },
          { status: 500 }
        );
      })
    );

    renderPage();

    await waitFor(() => {
      expect(
        screen.getByText("No se pudieron cargar las obligaciones.")
      ).toBeDefined();
    });
  });

  it("renders responsible select with member options", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/members`, () => {
        return HttpResponse.json([
          {
            user_id: 1,
            email: "owner@test.com",
            full_name: "Owner User",
            role: "owner",
            joined_at: "2026-01-01T00:00:00Z",
          },
          {
            user_id: 2,
            email: "member@test.com",
            full_name: "Member User",
            role: "member",
            joined_at: "2026-01-02T00:00:00Z",
          },
        ]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await userEvent.click(screen.getByText("+ Nueva obligación"));

    const select = screen.getByLabelText(/responsable/i);
    expect(select).toBeDefined();
    expect(screen.getByText("Sin asignar")).toBeDefined();
    expect(screen.getByText("Owner User")).toBeDefined();
    expect(screen.getByText("Member User")).toBeDefined();
  });

  it("creates obligation with responsible_user_id when selected", async () => {
    let postBody: Record<string, unknown> = {};

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/members`, () => {
        return HttpResponse.json([
          {
            user_id: 1,
            email: "owner@test.com",
            full_name: "Owner User",
            role: "owner",
            joined_at: "2026-01-01T00:00:00Z",
          },
          {
            user_id: 2,
            email: "member@test.com",
            full_name: "Member User",
            role: "member",
            joined_at: "2026-01-02T00:00:00Z",
          },
        ]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 2,
            group_id: 1,
            category_id: null,
            payment_method_id: null,
            responsible_user_id: postBody.responsible_user_id ?? null,
            name: postBody.name,
            provider_name: null,
            external_reference: null,
            notes: null,
            currency: "COP",
            expected_amount_cents: 0,
            is_variable_amount: false,
            is_subscription: false,
            auto_debit: false,
            is_essential: true,
            periodicity: "MONTHLY",
            due_day: 1,
            due_month: null,
            start_date: "2026-01-01",
            end_date: null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Netflix");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.selectOptions(screen.getByLabelText(/responsable/i), "2");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    await waitFor(() => {
      expect(postBody.responsible_user_id).toBe(2);
    });
  });

  it("creates obligation with null responsible_user_id when Sin asignar", async () => {
    let postBody: Record<string, unknown> = {};

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/members`, () => {
        return HttpResponse.json([
          {
            user_id: 1,
            email: "owner@test.com",
            full_name: "Owner User",
            role: "owner",
            joined_at: "2026-01-01T00:00:00Z",
          },
        ]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 2,
            group_id: 1,
            category_id: null,
            payment_method_id: null,
            responsible_user_id: null,
            name: postBody.name,
            provider_name: null,
            external_reference: null,
            notes: null,
            currency: "COP",
            expected_amount_cents: 0,
            is_variable_amount: false,
            is_subscription: false,
            auto_debit: false,
            is_essential: true,
            periodicity: "MONTHLY",
            due_day: 1,
            due_month: null,
            start_date: "2026-01-01",
            end_date: null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Netflix");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    await waitFor(() => {
      expect(postBody.responsible_user_id).toBeNull();
    });
  });

  it("renders category select with options", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/categories`, () => {
        return HttpResponse.json([
          {
            id: 1,
            group_id: null,
            name: "Servicios",
            icon: "🏠",
            is_system: true,
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: 2,
            group_id: null,
            name: "Entretenimiento",
            icon: null,
            is_system: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        ]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await userEvent.click(screen.getByText("+ Nueva obligación"));

    const select = screen.getByLabelText(/categoría/i);
    expect(select).toBeDefined();
    expect(screen.getByText("Sin categoría")).toBeDefined();
    expect(screen.getByText("🏠 Servicios")).toBeDefined();
    expect(screen.getByText("Entretenimiento")).toBeDefined();
  });

  it("renders payment method select with active options only", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/payment-methods`, () => {
        return HttpResponse.json([
          {
            id: 1,
            group_id: 1,
            kind: "CREDIT_CARD",
            provider_name: "Bancolombia",
            label: "Visa ****1234",
            last4: "1234",
            masked_key: null,
            holder_name: "Juan García",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
          {
            id: 2,
            group_id: 1,
            kind: "CASH",
            provider_name: "Efectivo",
            label: "Efectivo viejo",
            last4: null,
            masked_key: null,
            holder_name: "Juan García",
            is_active: false,
            created_at: "2026-01-01T00:00:00Z",
          },
        ]);
      })
    );

    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await userEvent.click(screen.getByText("+ Nueva obligación"));

    const select = screen.getByLabelText(/medio de pago/i);
    expect(select).toBeDefined();
    expect(screen.getByText("Sin especificar")).toBeDefined();
    expect(screen.getByText("Visa ****1234 (Bancolombia)")).toBeDefined();
    expect(screen.queryByText("Efectivo viejo (Efectivo)")).toBeNull();
  });

  it("creates obligation with category_id and payment_method_id when selected", async () => {
    let postBody: Record<string, unknown> = {};

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.get(`${API_BASE}/groups/:groupId/categories`, () => {
        return HttpResponse.json([
          {
            id: 1,
            group_id: null,
            name: "Servicios",
            icon: "🏠",
            is_system: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        ]);
      }),
      http.get(`${API_BASE}/groups/:groupId/payment-methods`, () => {
        return HttpResponse.json([
          {
            id: 1,
            group_id: 1,
            kind: "CREDIT_CARD",
            provider_name: "Bancolombia",
            label: "Visa ****1234",
            last4: "1234",
            masked_key: null,
            holder_name: "Juan García",
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
          },
        ]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 2,
            group_id: 1,
            category_id: postBody.category_id ?? null,
            payment_method_id: postBody.payment_method_id ?? null,
            responsible_user_id: null,
            name: postBody.name,
            provider_name: null,
            external_reference: null,
            notes: null,
            currency: "COP",
            expected_amount_cents: 0,
            is_variable_amount: false,
            is_subscription: false,
            auto_debit: false,
            is_essential: true,
            periodicity: "MONTHLY",
            due_day: 1,
            due_month: null,
            start_date: "2026-01-01",
            end_date: null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Netflix");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.selectOptions(screen.getByLabelText(/categoría/i), "1");
    await user.selectOptions(screen.getByLabelText(/medio de pago/i), "1");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    await waitFor(() => {
      expect(postBody.category_id).toBe(1);
      expect(postBody.payment_method_id).toBe(1);
    });
  });

  it("creates obligation with null category_id and payment_method_id when Sin categoría/Sin especificar", async () => {
    let postBody: Record<string, unknown> = {};

    server.use(
      http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
        return HttpResponse.json([]);
      }),
      http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
        postBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          {
            id: 2,
            group_id: 1,
            category_id: null,
            payment_method_id: null,
            responsible_user_id: null,
            name: postBody.name,
            provider_name: null,
            external_reference: null,
            notes: null,
            currency: "COP",
            expected_amount_cents: 0,
            is_variable_amount: false,
            is_subscription: false,
            auto_debit: false,
            is_essential: true,
            periodicity: "MONTHLY",
            due_day: 1,
            due_month: null,
            start_date: "2026-01-01",
            end_date: null,
            is_active: true,
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          { status: 201 }
        );
      })
    );

    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.queryByText(/cargando/i)).toBeNull();
    });

    await user.click(screen.getByText("+ Nueva obligación"));

    await user.type(screen.getByLabelText(/^nombre/i), "Netflix");
    await user.type(screen.getByLabelText(/fecha de inicio/i), "2026-01-01");

    await user.click(screen.getByRole("button", { name: /crear obligación/i }));

    await waitFor(() => {
      expect(postBody.category_id).toBeNull();
      expect(postBody.payment_method_id).toBeNull();
    });
  });
});
