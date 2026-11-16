import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/utils";
import type { AuditEvent, AuditPage } from "../types";

const ev = (i: number, over: Partial<AuditEvent> = {}): AuditEvent => ({
  id: `evt-${i}`, timestamp: "2026-11-11T10:00:00Z", actor: "agent-1", action: "analyze", module: "A", decision: "BLOCK", result: "bloqué", reference: `ref-${i}`, details: { reason: "règle override_fr" }, ...over,
});
const page = (items: AuditEvent[], over: Partial<AuditPage> = {}): AuditPage => ({ items, page: 0, size: 20, total: items.length, ...over });
const route = (body: AuditPage | (() => { body: AuditPage })) => ({ "GET /api/events": typeof body === "function" ? body : { body } });
const queryOf = (url: string) => new URLSearchParams(url.split("?")[1]);

describe("AuditTrail", () => {
  it("affiche les colonnes demandées et les événements", async () => {
    renderApp("/audit", route(page([ev(1), ev(2, { decision: "ALLOW", module: "B" })])));
    const table = await screen.findByRole("table");
    for (const col of ["Identifiant", "Date", "Utilisateur / agent", "Action", "Module", "Décision", "Résultat", "Référence"]) {
      expect(within(table).getByRole("columnheader", { name: col })).toBeInTheDocument();
    }
    expect(within(table).getByText("evt-1")).toBeInTheDocument();
    expect(within(table).getByText("Bloqué")).toBeInTheDocument();
  });

  it("est en lecture seule : aucun contrôle de création, modification ou suppression", async () => {
    renderApp("/audit", route(page([ev(1)])));
    await screen.findByRole("table");
    const names = screen.getAllByRole("button").map((b) => b.getAttribute("aria-label") ?? b.textContent ?? "");
    expect(names.join("|")).not.toMatch(/supprim|modifi|édit|edit|delete|ajout|créer|annuler l'événement/i);
    expect(screen.queryAllByRole("textbox").every((t) => t.closest("form[role='search']"))).toBe(true);
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("gère l'état vide", async () => {
    renderApp("/audit", route(page([])));
    expect(await screen.findByText(/Aucun événement ne correspond/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("gère l'erreur avec une nouvelle tentative", async () => {
    let n = 0;
    renderApp("/audit", route(() => (++n === 1 ? ({ status: 500 } as never) : { body: page([ev(1)]) })));
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByText("evt-1")).toBeInTheDocument();
  });

  it("applique recherche et filtres côté serveur", async () => {
    const { api } = renderApp("/audit", route(page([ev(1)])));
    await screen.findByRole("table");
    await userEvent.type(screen.getByLabelText("Recherche"), "ref-9");
    await userEvent.selectOptions(screen.getByLabelText("Module"), "D");
    await userEvent.selectOptions(screen.getByLabelText("Décision"), "BLOCK");
    await userEvent.click(screen.getByRole("button", { name: "Filtrer" }));
    await screen.findByRole("table");
    const last = queryOf(api.calls.filter((c) => c.url.startsWith("/api/events")).at(-1)!.url);
    expect(Object.fromEntries(last)).toMatchObject({ search: "ref-9", module: "D", decision: "BLOCK", page: "0" });
  });

  it("pagine : Suivant / Précédent demandent la bonne page", async () => {
    const { api } = renderApp("/audit", route(() => ({ body: page([ev(1)], { total: 45, page: Number(queryOf((globalThis.fetch as unknown as { mock: { calls: [string][] } }).mock.calls.at(-1)![0]).get("page")) }) })));
    await screen.findByText(/Page 1 sur 3/);
    expect(screen.getByRole("button", { name: "Précédent" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Suivant" }));
    await screen.findByText(/Page 2 sur 3/);
    expect(queryOf(api.calls.filter((c) => c.url.startsWith("/api/events")).at(-1)!.url).get("page")).toBe("1");
  });

  it("ouvre le détail d'un événement et le ferme", async () => {
    renderApp("/audit", route(page([ev(7)])));
    await userEvent.click(await screen.findByRole("button", { name: "Voir les détails de evt-7" }));
    const panel = screen.getByRole("complementary", { name: /evt-7/ });
    expect(within(panel).getByText("règle override_fr")).toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Fermer" }));
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
  });

  it("affiche en texte brut un contenu hostile (jamais interprété comme du HTML)", async () => {
    const hostile = `<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>`;
    renderApp("/audit", route(page([ev(1, { action: hostile, details: { extrait: hostile } })])));
    await userEvent.click(await screen.findByRole("button", { name: /détails de evt-1/ }));
    expect(document.querySelector("img")).toBeNull();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getAllByText(hostile).length).toBeGreaterThan(0);
    expect((window as unknown as { __pwned?: number }).__pwned).toBeUndefined();
  });

  it("depuis l'activité récente (?event=), préremplit la recherche sur l'identifiant", async () => {
    const { api } = renderApp("/audit?event=evt-42", route(page([ev(42)])));
    await screen.findByRole("table");
    expect(screen.getByLabelText("Recherche")).toHaveValue("evt-42");
    expect(queryOf(api.calls.find((c) => c.url.startsWith("/api/events"))!.url).get("search")).toBe("evt-42");
  });
});
