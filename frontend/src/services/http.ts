/**
 * Client HTTP. L'authentification repose sur un cookie de session HttpOnly posé par le backend :
 * l'interface ne lit, ne stocke ni ne transmet aucun jeton (pas de localStorage).
 * La protection CSRF est assurée par un en-tête dérivé du cookie `XSRF-TOKEN` (à confirmer avec É3, AS-S3-008).
 */
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

const BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

function csrfHeader(): Record<string, string> {
  const match = /(?:^|;\s*)XSRF-TOKEN=([^;]+)/.exec(document.cookie);
  return match ? { "X-XSRF-TOKEN": decodeURIComponent(match[1]) } : {};
}

export async function request<T>(path: string, init: RequestInit & { json?: unknown } = {}, signal?: AbortSignal): Promise<T> {
  const { json, headers, ...rest } = init;
  const method = (rest.method ?? "GET").toUpperCase();
  const response = await fetch(`${BASE}${path}`, {
    ...rest,
    method,
    signal,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(method !== "GET" ? csrfHeader() : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!response.ok) throw new ApiError(response.status, `HTTP ${response.status}`);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
