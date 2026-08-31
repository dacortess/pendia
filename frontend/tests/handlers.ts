import { http, HttpResponse, delay } from "msw";

const API_BASE = "http://localhost:8000/api/v1";

const mockUser = {
  id: 1,
  email: "test@example.com",
  full_name: "Test User",
  phone_number: null,
  whatsapp_opt_in: false,
  created_at: "2026-01-01T00:00:00Z",
};

export const handlers = [
  http.post(`${API_BASE}/auth/login`, async () => {
    return HttpResponse.json({
      access_token: "new-access-token",
      token_type: "bearer",
    });
  }),

  http.post(`${API_BASE}/auth/register`, async () => {
    return new HttpResponse(
      JSON.stringify({
        access_token: "new-access-token",
        token_type: "bearer",
      }),
      { status: 201 }
    );
  }),

  http.post(`${API_BASE}/auth/refresh`, async () => {
    return HttpResponse.json({
      access_token: "refreshed-token",
      token_type: "bearer",
    });
  }),

  http.post(`${API_BASE}/auth/logout`, async () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API_BASE}/users/me`, () => {
    return HttpResponse.json(mockUser);
  }),

  http.get(`${API_BASE}/groups`, () => {
    return HttpResponse.json([]);
  }),

  http.post(`${API_BASE}/groups`, async ({ request }) => {
    const body = (await request.json()) as { name: string };
    return HttpResponse.json(
      {
        id: 1,
        name: body.name,
        created_by: 1,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        my_role: "owner",
      },
      { status: 201 }
    );
  }),

  http.get(`${API_BASE}/groups/:groupId/obligations`, () => {
    return HttpResponse.json([]);
  }),

  http.get(`${API_BASE}/groups/:groupId/members`, () => {
    return HttpResponse.json([
      {
        user_id: 1,
        email: "test@example.com",
        full_name: "Test User",
        role: "owner",
        joined_at: "2026-01-01T00:00:00Z",
      },
      {
        user_id: 2,
        email: "other@example.com",
        full_name: "Other User",
        role: "member",
        joined_at: "2026-01-02T00:00:00Z",
      },
    ]);
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
      {
        id: 3,
        group_id: 1,
        name: "Transporte",
        icon: "🚗",
        is_system: false,
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
      {
        id: 2,
        group_id: 1,
        kind: "BANK_ACCOUNT",
        provider_name: "Nequi",
        label: "Cuenta principal",
        last4: null,
        masked_key: null,
        holder_name: "Juan García",
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
      },
      {
        id: 3,
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
  }),

  http.post(`${API_BASE}/groups/:groupId/obligations`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      {
        id: 1,
        group_id: Number(body.group_id) || 1,
        category_id: null,
        payment_method_id: null,
        responsible_user_id: null,
        provider_name: body.provider_name ?? null,
        external_reference: null,
        notes: body.notes ?? null,
        is_variable_amount: body.is_variable_amount ?? false,
        is_subscription: body.is_subscription ?? false,
        auto_debit: body.auto_debit ?? false,
        is_essential: body.is_essential ?? true,
        due_month: body.due_month ?? null,
        end_date: body.end_date ?? null,
        is_active: true,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        name: body.name,
        currency: body.currency ?? "COP",
        expected_amount_cents: body.expected_amount_cents ?? 0,
        periodicity: body.periodicity ?? "MONTHLY",
        due_day: body.due_day ?? 1,
        start_date: body.start_date ?? "2026-01-01",
      },
      { status: 201 }
    );
  }),

  http.get(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
    return HttpResponse.json(
      { detail: "Obligación no encontrada", code: "OBLIGATION_NOT_FOUND" },
      { status: 404 }
    );
  }),

  http.patch(`${API_BASE}/groups/:groupId/obligations/:id`, async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      id: 1,
      group_id: 1,
      category_id: null,
      payment_method_id: null,
      responsible_user_id: null,
      provider_name: body.provider_name ?? null,
      external_reference: null,
      notes: body.notes ?? null,
      is_variable_amount: body.is_variable_amount ?? false,
      is_subscription: body.is_subscription ?? false,
      auto_debit: body.auto_debit ?? false,
      is_essential: body.is_essential ?? true,
      due_month: body.due_month ?? null,
      end_date: body.end_date ?? null,
      is_active: true,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      name: body.name ?? "Obligación",
      currency: body.currency ?? "COP",
      expected_amount_cents: body.expected_amount_cents ?? 0,
      periodicity: body.periodicity ?? "MONTHLY",
      due_day: body.due_day ?? 1,
      start_date: body.start_date ?? "2026-01-01",
    });
  }),

  http.delete(`${API_BASE}/groups/:groupId/obligations/:id`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  http.get(`${API_BASE}/groups/:groupId/periods`, () => {
    return HttpResponse.json([]);
  }),

  http.post(
    `${API_BASE}/groups/:groupId/periods/:periodId/payments`,
    async ({ request }) => {
      const body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json({
        id: 1,
        obligation_period_id: 1,
        registered_by_user_id: 1,
        amount_cents: body.amount_cents ?? 0,
        currency: body.currency ?? "COP",
        paid_at: body.paid_at ?? "2026-01-01",
        notes: body.notes ?? null,
        receipt_url: body.receipt_url ?? null,
        voided_at: null,
        voided_by_user_id: null,
        created_at: "2026-01-01T00:00:00Z",
      });
    }
  ),

  http.get(`${API_BASE}/groups/:groupId/payments`, () => {
    return HttpResponse.json([]);
  }),
];

export { mockUser };
