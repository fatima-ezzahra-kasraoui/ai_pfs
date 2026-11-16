import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import App from "../App";
import { AuthProvider } from "../auth/AuthContext";
import type { SessionUser } from "../types";

export const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true } as const;

export const ANALYST: SessionUser = { username: "analyste", role: "ANALYST", email: "analyste@exemple.test" };

export type Reply = { status?: number; body?: unknown } | (() => { status?: number; body?: unknown });
export type Routes = Record<string, Reply>; // clé : « METHODE /chemin » (sans query)

export interface ApiMock {
  calls: { method: string; url: string; body?: unknown; headers: Record<string, string> }[];
}

/** Remplace `fetch` : toute route non déclarée répond 404 (aucun appel réseau réel). */
export function mockApi(routes: Routes): ApiMock {
  const mock: ApiMock = { calls: [] };
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const url = String(input);
    const method = (init?.method ?? "GET").toUpperCase();
    mock.calls.push({ method, url, body: init?.body ? JSON.parse(String(init.body)) : undefined, headers: (init?.headers ?? {}) as Record<string, string> });
    const path = url.split("?")[0];
    const reply = routes[`${method} ${path}`];
    if (!reply) return new Response("not found", { status: 404 });
    const { status = 200, body } = typeof reply === "function" ? reply() : reply;
    return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  });
  return mock;
}

export function renderApp(path: string, routes: Routes, { loggedIn = true }: { loggedIn?: boolean } = {}) {
  const api = mockApi({ "GET /api/auth/me": loggedIn ? { body: ANALYST } : { status: 401 }, ...routes });
  const utils = render(
    <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </MemoryRouter>,
  );
  return { api, ...utils };
}
