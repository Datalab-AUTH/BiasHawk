/**
 * The API client.
 *
 * Auth is a Django session cookie, so every request sends credentials and no
 * token is ever held in JavaScript. Unsafe methods echo the CSRF cookie back in
 * the X-CSRFToken header, which Django checks against the cookie.
 */

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }

  /** Field errors from a DRF serializer, if this was a validation failure. */
  get fieldErrors(): Record<string, string[]> {
    if (this.detail && typeof this.detail === "object" && !Array.isArray(this.detail)) {
      return this.detail as Record<string, string[]>;
    }
    return {};
  }
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(^|;\\s*)${name}=([^;]*)`));
  return match ? decodeURIComponent(match[2]) : null;
}

let csrfPromise: Promise<string | null> | null = null;

/**
 * The CSRF token, fetching it once if the cookie is not already set.
 * Concurrent callers share one in-flight request.
 */
export async function ensureCsrfToken(): Promise<string> {
  const existing = readCookie("csrftoken");
  if (existing) return existing;

  if (!csrfPromise) {
    csrfPromise = fetch(`${BASE}/csrf`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.csrfToken ?? readCookie("csrftoken"))
      .finally(() => {
        csrfPromise = null;
      });
  }
  return (await csrfPromise) ?? "";
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
};

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const method = options.method ?? "GET";
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;

  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const token = await ensureCsrfToken();
    if (token) headers["X-CSRFToken"] = token;
  }

  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body,
    credentials: "include",
    signal: options.signal,
  });

  if (response.status === 204) return undefined as T;

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json")
    ? await response.json().catch(() => null)
    : await response.text();

  if (!response.ok) {
    const message =
      (payload && typeof payload === "object" && "detail" in payload
        ? String((payload as { detail: unknown }).detail)
        : null) ?? `Request failed (${response.status})`;
    throw new ApiError(response.status, payload, message);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  /** Absolute URL for a link the browser follows itself, such as a PDF. */
  url: (path: string) => `${BASE}${path}`,
};

/**
 * allauth's headless endpoints sit outside /api, so they get their own caller.
 * Its 401 for "not signed in" is a normal state, not an error.
 */
const ALLAUTH = BASE.replace(/\/api\/?$/, "") + "/_allauth/browser/v1";

async function allauthRequest<T>(path: string, method: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = await ensureCsrfToken();
  if (token) headers["X-CSRFToken"] = token;

  const response = await fetch(`${ALLAUTH}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "include",
  });

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const errors = (payload as { errors?: { message: string }[] } | null)?.errors;
    const message = errors?.map((e) => e.message).join(" ") || `Request failed (${response.status})`;
    throw new ApiError(response.status, payload, message);
  }
  return payload as T;
}

export const auth = {
  signUp: (email: string, password: string) =>
    allauthRequest("/auth/signup", "POST", { email, password }),
  signIn: (email: string, password: string) =>
    allauthRequest("/auth/login", "POST", { email, password }),
  signOut: () => allauthRequest("/auth/session", "DELETE").catch(() => null),
  config: () => allauthRequest<AllauthConfig>("/config", "GET"),
  /** Starts an OAuth flow by form POST, because it ends in a cross-origin redirect. */
  providerRedirectUrl: `${ALLAUTH}/auth/provider/redirect`,
};

export type AllauthConfig = {
  data?: { socialaccount?: { providers?: { id: string; name: string }[] } };
};
