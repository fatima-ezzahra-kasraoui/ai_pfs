import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/utils";
import { redact } from "./Settings";

const policy = {
  thresholds: { injection_block: 0.9, injection_review: 0.5, coherence_min: 0.4 },
  tools: { delete_file: { risk: "high", allowed: true, require_confirmation: true } },
  output: { canary_tokens: ["sk-FAKE-1234"], on_secret_detected: "SANITIZE", api_key: "sk-SECRET-DEMO-VALUE" },
};
const routes = { "GET /api/policy": { body: policy } };

describe("Settings", () => {
  it("affiche le profil issu de /api/auth/me", async () => {
    renderApp("/settings", routes);
    const profile = await screen.findByRole("region", { name: "Profil" });
    expect(await within(profile).findByText("analyste")).toBeInTheDocument();
    expect(within(profile).getByText("ANALYST")).toBeInTheDocument();
  });

  it("affiche les politiques en lecture seule, sans proposer de les modifier", async () => {
    renderApp("/settings", routes);
    const section = await screen.findByRole("region", { name: "Politiques en vigueur" });
    expect(await within(section).findByText("injection_block")).toBeInTheDocument();
    expect(within(section).getByText("0.9")).toBeInTheDocument();
    expect(within(section).queryByRole("textbox")).not.toBeInTheDocument();
    expect(within(section).queryByRole("spinbutton")).not.toBeInTheDocument();
    expect(within(section).queryByRole("button")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /enregistrer|modifier|appliquer/i })).not.toBeInTheDocument();
  });

  it("n'affiche aucun secret (canary, clés)", async () => {
    renderApp("/settings", routes);
    await screen.findByText("injection_block");
    expect(document.body.textContent).not.toContain("sk-FAKE-1234");
    expect(document.body.textContent).not.toContain("sk-SECRET-DEMO-VALUE");
    expect(document.body.textContent).toContain("masquée");
  });

  it("redact masque toute clé évoquant un secret, récursivement", () => {
    expect(redact({ a: { password: "x", token: ["t1", "t2"], ok: 1 }, list: [{ api_key: "k" }] })).toEqual({
      a: { password: "••••", token: "•••• (2 valeur(s) masquée(s))", ok: 1 },
      list: [{ api_key: "••••" }],
    });
  });

  it("changer de thème l'applique et mémorise uniquement la préférence", async () => {
    renderApp("/settings", routes);
    await userEvent.selectOptions(await screen.findByLabelText("Thème"), "dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(window.localStorage.getItem("agentshield.theme")).toBe("dark");
    expect(window.localStorage.length).toBe(1);
    await userEvent.selectOptions(screen.getByLabelText("Thème"), "system");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("gère une politique vide et une erreur serveur", async () => {
    const { unmount } = renderApp("/settings", { "GET /api/policy": { body: {} } });
    expect(await screen.findByText("Aucune politique à afficher.")).toBeInTheDocument();
    unmount();
    renderApp("/settings", { "GET /api/policy": { status: 500 } });
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
