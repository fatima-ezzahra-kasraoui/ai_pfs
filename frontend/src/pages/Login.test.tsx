import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ANALYST, renderApp } from "../test/utils";
import { loginSchema, safeRedirect } from "./Login";

describe("Login", () => {
  it("valide le formulaire : champs obligatoires", async () => {
    const { api } = renderApp("/login", {}, { loggedIn: false });
    await userEvent.click(await screen.findByRole("button", { name: "Se connecter" }));
    expect(await screen.findByText("Identifiant requis")).toBeInTheDocument();
    expect(screen.getByText("Mot de passe requis")).toBeInTheDocument();
    expect(api.calls.some((c) => c.url === "/api/auth/login")).toBe(false);
  });

  it("affiche un message d'erreur générique, quel que soit l'échec", async () => {
    for (const status of [401, 403, 500]) {
      const { unmount } = renderApp("/login", { "POST /api/auth/login": { status } }, { loggedIn: false });
      await userEvent.type(await screen.findByLabelText("Identifiant"), "alice");
      await userEvent.type(screen.getByLabelText("Mot de passe"), "mauvais");
      await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
      const alert = await screen.findByText("Identifiants invalides.");
      expect(alert).toBeInTheDocument();
      expect(document.body.textContent).not.toMatch(/401|403|500|inconnu|n'existe pas|mot de passe incorrect/i);
      unmount();
    }
  });

  it("redirige vers la page demandée après connexion, sans jeton dans le navigateur", async () => {
    const routes = {
      "POST /api/auth/login": { body: ANALYST },
      "GET /api/dashboard/overview": { body: { totalRequests: 0, attacksDetected: 0, blockedActions: 0, sanitizedActions: 0, pendingConfirmations: 0, asr: null, attacksOverTime: [], decisions: {}, byCategory: {}, bySeverity: {}, recent: [] } },
      "GET /api/events": { body: { items: [], page: 0, size: 20, total: 0 } },
    };
    // /audit demandée sans session : redirection vers /login puis retour sur /audit
    const { api } = renderApp("/audit", routes, { loggedIn: false });
    await userEvent.type(await screen.findByLabelText("Identifiant"), "analyste");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "secret-de-test");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("heading", { name: "Journal d'audit" })).toBeInTheDocument();
    expect(window.localStorage.length).toBe(0);
    expect(window.sessionStorage.length).toBe(0);
    expect(document.cookie).not.toMatch(/token|jwt/i);
    const login = api.calls.find((c) => c.url === "/api/auth/login");
    expect(login?.body).toEqual({ username: "analyste", password: "secret-de-test" });
  });

  it("envoie les identifiants avec les cookies de session (credentials: include)", async () => {
    const { api } = renderApp("/login", { "POST /api/auth/login": { body: ANALYST } }, { loggedIn: false });
    await userEvent.type(await screen.findByLabelText("Identifiant"), "a");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "b");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    await waitFor(() => expect(api.calls.some((c) => c.method === "POST")).toBe(true));
  });

  it("ne redirige jamais vers un site externe (redirection ouverte)", () => {
    expect(safeRedirect("/audit?event=1")).toBe("/audit?event=1");
    for (const bad of ["//evil.test", "https://evil.test", "/\\evil.test", "javascript:alert(1)", undefined, 42]) expect(safeRedirect(bad)).toBe("/");
  });

  it("le schéma refuse un identifiant composé d'espaces", () => {
    expect(loginSchema.safeParse({ username: "   ", password: "x" }).success).toBe(false);
    expect(loginSchema.safeParse({ username: "a", password: "x" }).success).toBe(true);
  });

  it("route protégée : redirige vers /login sans session", async () => {
    renderApp("/settings", {}, { loggedIn: false });
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeInTheDocument();
  });
});
