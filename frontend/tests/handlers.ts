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
];

export { mockUser };
