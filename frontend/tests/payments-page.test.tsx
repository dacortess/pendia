import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import React from "react";
import PaymentsPage from "@/app/(app)/payments/page";
import { AuthProvider } from "@/lib/auth-context";
import { GroupProvider } from "@/lib/groups-context";
import { server } from "./server";
import { mockUser } from "./handlers";

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

const mockPeriod = {
  id: 1,
  obligation_id: 1,
  period_month: "2026-08",
  due_date: "2026-08-15",
  status: "PENDIENTE" as const,
  created_at: "2026-08-01T00:00:00Z",
};

const mockPaidPeriod = {
  ...mockPeriod,
  id: 2,
  status: "PAGADO" as const,
};

const mockPayment = {
  id: 1,
  obligation_period_id: 1,
  registered_by_user_id: 1,
  amount_cents: 89900,
  currency: "COP" as const,
  paid_at: "2026-08-10",
  notes: null,
  receipt_url: null,
  voided_at: null,
  voided_by_user_id: null,
  created_at: "2026-08-10T00:00:00Z",
};

afterEach(() => {
  localStorage.clear();
});

function renderPage(
  group = mockGroup,
  periods = [mockPeriod],
  obligations = [mockObligation],
  payments: Array<{
    id: number;
    obligation_period_id: number;
    registered_by_user_id: number;
    amount_cents: number;
    currency: "COP" | "USD";
    paid_at: string;
    notes: string | null;
    receipt_url: string | null;
    voided_at: string | null;
    voided_by_user_id: number | null;
    created_at: string;
  }> = []
) {
  server.use(
    http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
      return HttpResponse.json(obligations);
    }),
    http.get(`${API_BASE}/groups/:groupId/periods`, () => {
      return HttpResponse.json(periods);
    }),
    http.get(`${API_BASE}/groups/:groupId/payments`, () => {
      return HttpResponse.json(payments);
    })
  );

  return render(
    <AuthProvider>
      <GroupProvider
        initialState={{
          groups: [group],
          currentGroupId: group.id,
          loading: false,
        }}
      >
        <PaymentsPage />
      </GroupProvider>
    </AuthProvider>
  );
}

describe("PaymentsPage", () => {
  it("shows 'No hay pagos pendientes.' when filtered list is empty", async () => {
    renderPage(mockGroup, []);

    await waitFor(() => {
      expect(
        screen.getByText("No hay pagos pendientes.")
      ).toBeDefined();
    });
  });

  it("renders row with obligation name, formatted amount, date, and status badge", async () => {
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    expect(screen.getByText("Pendiente")).toBeDefined();
    expect(screen.getByText("15/08/2026")).toBeDefined();
  });

  it("does NOT show PAGADO periods in the list", async () => {
    renderPage(mockGroup, [mockPeriod, mockPaidPeriod]);

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    expect(screen.queryByText("No hay pagos pendientes.")).toBeNull();
  });

  it("shows 'Registrar pago' button when my_role is owner", async () => {
    renderPage(mockGroup);

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });
  });

  it("shows 'Registrar pago' button when member and responsible_user_id matches user id", async () => {
    const obligationWithResponsible = {
      ...mockObligation,
      responsible_user_id: mockUser.id,
    };

    renderPage(mockMemberGroup, [mockPeriod], [obligationWithResponsible]);

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });
  });

  it("does NOT show 'Registrar pago' button when member and responsible_user_id is null", async () => {
    renderPage(mockMemberGroup);

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    expect(screen.queryByText("Registrar pago")).toBeNull();
  });

  it("does NOT show 'Registrar pago' button when member and responsible_user_id differs", async () => {
    const obligationOther = {
      ...mockObligation,
      responsible_user_id: 999,
    };

    renderPage(mockMemberGroup, [mockPeriod], [obligationOther]);

    await waitFor(() => {
      expect(screen.getByText("Internet mensual")).toBeDefined();
    });

    expect(screen.queryByText("Registrar pago")).toBeNull();
  });

  it("registers payment and removes period from list on success", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Registrar pago"));

    await waitFor(() => {
      expect(screen.getByText("Confirmar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar pago"));

    await waitFor(() => {
      expect(
        screen.getByText("No hay pagos pendientes.")
      ).toBeDefined();
    });
  });

  it("shows error and removes period on PERIOD_ALREADY_PAID", async () => {
    const user = userEvent.setup();

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/periods/:periodId/payments`,
        () => {
          return HttpResponse.json(
            { detail: "Período ya pagado", code: "PERIOD_ALREADY_PAID" },
            { status: 409 }
          );
        }
      )
    );

    await user.click(screen.getByText("Registrar pago"));

    await waitFor(() => {
      expect(screen.getByText("Confirmar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar pago"));

    await waitFor(() => {
      expect(
        screen.getByText("Este período ya tiene un pago registrado.")
      ).toBeDefined();
    });

    expect(screen.queryByText("Internet mensual")).toBeNull();
  });

  it("shows specific error on FORBIDDEN_NOT_RESPONSIBLE", async () => {
    const user = userEvent.setup();

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/periods/:periodId/payments`,
        () => {
          return HttpResponse.json(
            {
              detail: "No tienes permisos",
              code: "FORBIDDEN_NOT_RESPONSIBLE",
            },
            { status: 403 }
          );
        }
      )
    );

    await user.click(screen.getByText("Registrar pago"));

    await waitFor(() => {
      expect(screen.getByText("Confirmar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar pago"));

    await waitFor(() => {
      expect(
        screen.getByText(
          "No tienes permisos para registrar este pago."
        )
      ).toBeDefined();
    });
  });

  it("sends currency matching the obligation currency", async () => {
    const user = userEvent.setup();
    let capturedBody: Record<string, unknown> | null = null;

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/periods/:periodId/payments`,
        async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json({
            id: 1,
            obligation_period_id: 1,
            registered_by_user_id: 1,
            amount_cents: capturedBody.amount_cents ?? 0,
            currency: capturedBody.currency ?? "COP",
            paid_at: capturedBody.paid_at ?? "2026-01-01",
            notes: capturedBody.notes ?? null,
            receipt_url: capturedBody.receipt_url ?? null,
            voided_at: null,
            voided_by_user_id: null,
            created_at: "2026-01-01T00:00:00Z",
          });
        }
      )
    );

    await user.click(screen.getByText("Registrar pago"));

    await waitFor(() => {
      expect(screen.getByText("Confirmar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar pago"));

    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
    });

    expect(capturedBody!.currency).toBe(mockObligation.currency);
  });

  it("shows no-group prompt when currentGroup is null", async () => {
    server.use(
      http.get(`${API_BASE}/groups`, () => {
        return HttpResponse.json([]);
      })
    );

    render(
      <AuthProvider>
        <GroupProvider
          initialState={{
            groups: [],
            currentGroupId: null,
            loading: false,
          }}
        >
          <PaymentsPage />
        </GroupProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          /Primero creá un grupo desde el Dashboard antes de ver pagos/
        )
      ).toBeDefined();
    });
  });

  it("shows load error when API fails", async () => {
    server.use(
      http.get(`${API_BASE}/groups/:groupId/periods`, () => {
        return HttpResponse.json(
          { detail: "Error", code: "UNKNOWN_ERROR" },
          { status: 500 }
        );
      })
    );

    render(
      <AuthProvider>
        <GroupProvider
          initialState={{
            groups: [mockGroup],
            currentGroupId: mockGroup.id,
            loading: false,
          }}
        >
          <PaymentsPage />
        </GroupProvider>
      </AuthProvider>
    );

    await waitFor(() => {
      expect(
        screen.getByText(
          "No se pudieron cargar los pagos pendientes."
        )
      ).toBeDefined();
    });
  });

  it("excludes periods whose obligation no longer exists", async () => {
    const orphanPeriod = { ...mockPeriod, obligation_id: 999 };

    renderPage(mockGroup, [orphanPeriod], [mockObligation]);

    await waitFor(() => {
      expect(screen.getByText("No hay pagos pendientes.")).toBeDefined();
    });

    expect(screen.queryByText("Internet mensual")).toBeNull();
  });

  it("prefills 'Monto pagado' with the obligation's expected amount", async () => {
    const user = userEvent.setup();
    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Registrar pago"));

    const amountInput = await screen.findByLabelText(/monto pagado/i);
    expect(amountInput).toHaveValue(899);
  });

  it("cancel closes the form without calling the payments endpoint", async () => {
    const user = userEvent.setup();
    let postCalled = false;

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Registrar pago")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/periods/:periodId/payments`,
        () => {
          postCalled = true;
          return HttpResponse.json({ id: 1 }, { status: 201 });
        }
      )
    );

    await user.click(screen.getByText("Registrar pago"));

    await waitFor(() => {
      expect(screen.getByText("Confirmar pago")).toBeDefined();
    });

    await user.click(screen.getByText("Cancelar"));

    expect(screen.queryByText("Confirmar pago")).toBeNull();
    expect(postCalled).toBe(false);
  });

  it("shows 'Aún no hay pagos registrados.' when payments list is empty", async () => {
    renderPage(mockGroup, [mockPeriod], [mockObligation], []);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getByText("Aún no hay pagos registrados.")).toBeDefined();
  });

  it("renders a history row with obligation name, amount, date, and active badge", async () => {
    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getAllByText("Internet mensual").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Activo")).toBeDefined();
    expect(screen.getByText("10/08/2026")).toBeDefined();
  });

  it("shows 'Anulado' badge and no 'Anular' button for voided payment", async () => {
    const voidedPayment = {
      ...mockPayment,
      voided_at: "2026-08-12T00:00:00Z",
      voided_by_user_id: 1,
    };

    renderPage(mockGroup, [mockPeriod], [mockObligation], [voidedPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getByText("Anulado")).toBeDefined();
    expect(screen.queryByText("Anular")).toBeNull();
  });

  it("shows 'Obligación eliminada' for payment with no matching period", async () => {
    const orphanPayment = { ...mockPayment, obligation_period_id: 999 };

    renderPage(mockGroup, [mockPeriod], [mockObligation], [orphanPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getByText("Obligación eliminada")).toBeDefined();
    expect(screen.queryByText("Anular")).toBeNull();
  });

  it("shows 'Anular' button for owner on active payment", async () => {
    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getByText("Anular")).toBeDefined();
  });

  it("shows 'Anular' button for member when responsible_user_id matches", async () => {
    const obligationWithResponsible = {
      ...mockObligation,
      responsible_user_id: mockUser.id,
    };

    renderPage(
      mockMemberGroup,
      [mockPeriod],
      [obligationWithResponsible],
      [mockPayment]
    );

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.getByText("Anular")).toBeDefined();
  });

  it("hides 'Anular' button for member when not responsible", async () => {
    renderPage(mockMemberGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    expect(screen.queryByText("Anular")).toBeNull();
  });

  it("click 'Anular' then 'Cancelar' hides confirmation without calling void endpoint", async () => {
    const user = userEvent.setup();
    let voidCalled = false;

    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/payments/:paymentId/void`,
        () => {
          voidCalled = true;
          return HttpResponse.json({
            ...mockPayment,
            voided_at: "2026-08-12T00:00:00Z",
            voided_by_user_id: 1,
          });
        }
      )
    );

    await user.click(screen.getByText("Anular"));

    await waitFor(() => {
      expect(
        screen.getByText(
          /¿Anular este pago\? El período volverá a quedar pendiente/
        )
      ).toBeDefined();
    });

    await user.click(screen.getByText("Cancelar"));

    expect(screen.queryByText("Confirmar")).toBeNull();
    expect(voidCalled).toBe(false);
  });

  it("click 'Anular' then 'Confirmar' calls void endpoint and marks payment as Anulado", async () => {
    const user = userEvent.setup();

    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/payments/:paymentId/void`,
        () => {
          return HttpResponse.json({
            ...mockPayment,
            voided_at: "2026-08-12T00:00:00Z",
            voided_by_user_id: 1,
          });
        }
      )
    );

    await user.click(screen.getByText("Anular"));

    await waitFor(() => {
      expect(
        screen.getByText(
          /¿Anular este pago\? El período volverá a quedar pendiente/
        )
      ).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar"));

    await waitFor(() => {
      expect(screen.getByText("Anulado")).toBeDefined();
    });

    expect(screen.queryByText("Anular")).toBeNull();
  });

  it("shows FORBIDDEN_NOT_RESPONSIBLE error when voiding without permission", async () => {
    const user = userEvent.setup();

    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/payments/:paymentId/void`,
        () => {
          return HttpResponse.json(
            {
              detail: "No tienes permisos",
              code: "FORBIDDEN_NOT_RESPONSIBLE",
            },
            { status: 403 }
          );
        }
      )
    );

    await user.click(screen.getByText("Anular"));

    await waitFor(() => {
      expect(
        screen.getByText(
          /¿Anular este pago\? El período volverá a quedar pendiente/
        )
      ).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar"));

    await waitFor(() => {
      expect(
        screen.getByText("No tienes permisos para anular este pago.")
      ).toBeDefined();
    });
  });

  it("shows PAYMENT_ALREADY_VOIDED error and marks payment as Anulado", async () => {
    const user = userEvent.setup();

    renderPage(mockGroup, [mockPeriod], [mockObligation], [mockPayment]);

    await waitFor(() => {
      expect(screen.getByText("Historial de pagos")).toBeDefined();
    });

    server.use(
      http.post(
        `${API_BASE}/groups/:groupId/payments/:paymentId/void`,
        () => {
          return HttpResponse.json(
            {
              detail: "Pago ya anulado",
              code: "PAYMENT_ALREADY_VOIDED",
            },
            { status: 409 }
          );
        }
      )
    );

    await user.click(screen.getByText("Anular"));

    await waitFor(() => {
      expect(
        screen.getByText(
          /¿Anular este pago\? El período volverá a quedar pendiente/
        )
      ).toBeDefined();
    });

    await user.click(screen.getByText("Confirmar"));

    await waitFor(() => {
      expect(screen.getByText("Este pago ya fue anulado.")).toBeDefined();
    });

    expect(screen.getByText("Anulado")).toBeDefined();
    expect(screen.queryByText("Anular")).toBeNull();
  });
});
