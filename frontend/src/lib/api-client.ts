const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const EXCLUDE_REFRESH_PATHS = ["/auth/login", "/auth/register", "/auth/refresh"];

export class ApiError extends Error {
  detail: string;
  code: string;
  status: number;

  constructor(detail: string, code: string, status: number) {
    super(detail);
    this.name = "ApiError";
    this.detail = detail;
    this.code = code;
    this.status = status;
  }
}

interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  phone_number: string | null;
  whatsapp_opt_in: boolean;
  created_at: string;
}

interface AccessTokenResponse {
  access_token: string;
  token_type: string;
}

let accessTokenGetter: (() => string | null) | null = null;
let accessTokenSetter: ((token: string | null) => void) | null = null;
let onRefreshFailedCallback: (() => void) | null = null;

export function configureAuth({
  getToken,
  setToken,
  onRefreshFailed,
}: {
  getToken: () => string | null;
  setToken: (token: string | null) => void;
  onRefreshFailed: () => void;
}) {
  accessTokenGetter = getToken;
  accessTokenSetter = setToken;
  onRefreshFailedCallback = onRefreshFailed;
  refreshPromise = null;
  queuedRequests = [];
}

function getAccessToken(): string | null {
  return accessTokenGetter?.() ?? null;
}

function setAccessToken(token: string | null): void {
  accessTokenSetter?.(token);
}

function onRefreshFailed() {
  onRefreshFailedCallback?.();
}

type QueuedRequest = {
  resolve: (token: string) => void;
  reject: (error: Error) => void;
};

let refreshPromise: Promise<string> | null = null;
let queuedRequests: QueuedRequest[] = [];

async function performRefresh(): Promise<string> {
  const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
  });

  if (!res.ok) {
    throw new ApiError("Refresh failed", "REFRESH_FAILED", res.status);
  }

  const data: AccessTokenResponse = await res.json();
  return data.access_token;
}

async function refreshAccessToken(): Promise<string> {
  if (refreshPromise) {
    return refreshPromise;
  }

  refreshPromise = (async () => {
    try {
      const newToken = await performRefresh();
      setAccessToken(newToken);
      for (const queued of queuedRequests) {
        queued.resolve(newToken);
      }
      queuedRequests = [];
      return newToken;
    } catch (err) {
      setAccessToken(null);
      onRefreshFailed();
      const error =
        err instanceof ApiError ? err : new Error("Refresh failed");
      for (const queued of queuedRequests) {
        queued.reject(error);
      }
      queuedRequests = [];
      throw err;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getAccessToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && !EXCLUDE_REFRESH_PATHS.includes(path)) {
    try {
      const newToken = await refreshAccessToken();
      headers.set("Authorization", `Bearer ${newToken}`);
      const retryRes = await fetch(`${API_BASE_URL}${path}`, {
        ...options,
        headers,
      });
      return handleResponse<T>(retryRes);
    } catch {
      throw new ApiError("Unauthorized", "UNAUTHORIZED", 401);
    }
  }

  return handleResponse<T>(res);
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = "Request failed";
    let code = "UNKNOWN_ERROR";
    try {
      const body = await res.json();
      if (body && typeof body === "object") {
        detail = body.detail || detail;
        code = body.code || code;
      }
    } catch {
      // response body is not JSON
    }
    throw new ApiError(detail, code, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export async function login(
  email: string,
  password: string
): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/auth/login", {
    method: "POST",
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(data: {
  email: string;
  password: string;
  full_name: string;
  phone_number?: string;
  invite_code?: string;
}): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/auth/register", {
    method: "POST",
    credentials: "include",
    body: JSON.stringify(data),
  });
}

export async function refreshToken(): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/auth/refresh", {
    method: "POST",
    credentials: "include",
  });
}

export async function logout(): Promise<void> {
  return apiFetch<void>("/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

export async function getMe(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/users/me");
}

export interface Obligation {
  id: number;
  group_id: number;
  category_id: number | null;
  payment_method_id: number | null;
  responsible_user_id: number | null;
  name: string;
  provider_name: string | null;
  external_reference: string | null;
  notes: string | null;
  currency: "COP" | "USD";
  expected_amount_cents: number;
  is_variable_amount: boolean;
  is_subscription: boolean;
  auto_debit: boolean;
  is_essential: boolean;
  periodicity: "MONTHLY" | "BIMONTHLY" | "QUARTERLY" | "SEMIANNUAL" | "ANNUAL";
  due_day: number;
  due_month: number | null;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ObligationCreateInput {
  name: string;
  provider_name?: string;
  notes?: string;
  currency: "COP" | "USD";
  expected_amount_cents: number;
  is_variable_amount: boolean;
  is_subscription: boolean;
  auto_debit: boolean;
  is_essential: boolean;
  periodicity: "MONTHLY" | "BIMONTHLY" | "QUARTERLY" | "SEMIANNUAL" | "ANNUAL";
  due_day: number;
  due_month?: number | null;
  start_date: string;
  end_date?: string | null;
}

export async function listObligations(
  groupId: number
): Promise<Obligation[]> {
  return apiFetch<Obligation[]>(`/groups/${groupId}/obligations`);
}

export async function createObligation(
  groupId: number,
  data: ObligationCreateInput
): Promise<Obligation> {
  return apiFetch<Obligation>(`/groups/${groupId}/obligations`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export interface ObligationUpdateInput {
  name?: string;
  provider_name?: string | null;
  notes?: string | null;
  currency?: "COP" | "USD";
  expected_amount_cents?: number;
  is_variable_amount?: boolean;
  is_subscription?: boolean;
  auto_debit?: boolean;
  is_essential?: boolean;
  periodicity?: "MONTHLY" | "BIMONTHLY" | "QUARTERLY" | "SEMIANNUAL" | "ANNUAL";
  due_day?: number;
  due_month?: number | null;
  start_date?: string;
  end_date?: string | null;
}

export async function getObligation(
  groupId: number,
  id: number
): Promise<Obligation> {
  return apiFetch<Obligation>(`/groups/${groupId}/obligations/${id}`);
}

export async function updateObligation(
  groupId: number,
  id: number,
  data: ObligationUpdateInput
): Promise<Obligation> {
  return apiFetch<Obligation>(`/groups/${groupId}/obligations/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deactivateObligation(
  groupId: number,
  id: number
): Promise<void> {
  return apiFetch<void>(`/groups/${groupId}/obligations/${id}`, {
    method: "DELETE",
  });
}

export interface ObligationPeriod {
  id: number;
  obligation_id: number;
  period_month: string;
  due_date: string;
  status: "PENDIENTE" | "PAGADO" | "VENCIDO";
  created_at: string;
}

export async function listPeriods(groupId: number): Promise<ObligationPeriod[]> {
  return apiFetch<ObligationPeriod[]>(`/groups/${groupId}/periods`);
}

export interface PaymentCreateInput {
  amount_cents: number;
  currency: "COP" | "USD";
  paid_at: string;
  notes?: string;
  receipt_url?: string;
}

export interface Payment {
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
}

export async function registerPayment(
  groupId: number,
  periodId: number,
  data: PaymentCreateInput
): Promise<Payment> {
  return apiFetch<Payment>(`/groups/${groupId}/periods/${periodId}/payments`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listPayments(groupId: number): Promise<Payment[]> {
  return apiFetch<Payment[]>(`/groups/${groupId}/payments`);
}

export async function voidPayment(
  groupId: number,
  paymentId: number
): Promise<Payment> {
  return apiFetch<Payment>(`/groups/${groupId}/payments/${paymentId}/void`, {
    method: "POST",
  });
}
