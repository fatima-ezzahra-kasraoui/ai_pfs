import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { Overview, SystemHealth } from "../types";
import { renderApp } from "../test/utils";

const base: Overview = {
  totalRequests: 1234,
  attacksDetected: 87,
  blockedActions: 41,
  sanitizedActions: 12,
  pendingConfirmations: 3,
  asr: null,
  attacksOverTime: [{ date: "2026-11-10", count: 5 }, { date: "2026-11-11", count: 9 }],
  decisions: { ALLOW: 1100, BLOCK: 41, CONFIRM: 3, SANITIZE: 12 },
  byCategory: { direct_injection: 30, indirect_injection: 40, data_leak: 10, tool_abuse: 7 },
  bySeverity: { low: 10, medium: 30, high: 47 },
  recent: [{ id: "evt-42", timestamp: "2026-11-11T10:00:00Z", module: "A", decision: "BLOCK", attackType: "direct_injection", summary: "Injection directe bloquée" }],
};
const health: SystemHealth = { services: [{ name: "Backend", status: "UP" }, { name: "Service IA", status: "DOWN", detail: "timeout" }] };
const routes = (o: Partial<Overview> = {}, h: SystemHealth = health) => ({
  "GET /api/dashboard/overview": { body: { ...base, ...o } },
  "GET /api/system/health": { body: h },
});

describe("Overview", () => {
  it("affiche l'état de chargement puis les six cartes issues du backend", async () => {
    renderApp("/", routes());
    expect((await screen.findAllByText("Chargement…")).length).toBeGreaterThan(0);
    const card = async (name: string) => within(await screen.findByRole("article", { name }));
    expect((await card("Requêtes analysées")).getByText("1 234")).toBeInTheDocument();
    expect((await card("Attaques détectées")).getByText("87")).toBeInTheDocument();
    expect((await card("Actions bloquées")).getByText("41")).toBeInTheDocument();
    expect((await card("Contenus nettoyés")).getByText("12")).toBeInTheDocument();
    expect((await card("Confirmations en attente")).getByText("3")).toBeInTheDocument();
    expect(screen.getAllByRole("article").length).toBeGreaterThanOrEqual(6);
  });

  it("aucune valeur codée en dur : d'autres données donnent d'autres chiffres", async () => {
    renderApp("/", routes({ totalRequests: 7, attacksDetected: 2 }));
    expect(await within(await screen.findByRole("article", { name: "Requêtes analysées" })).findByText("7")).toBeInTheDocument();
    expect(screen.queryByText("1 234")).not.toBeInTheDocument();
  });

  it("l'ASR affiche « Évaluation à venir » tant qu'il n'est pas mesuré, et la valeur sinon", async () => {
    const { unmount } = renderApp("/", routes({ asr: null }));
    expect(await within(await screen.findByRole("article", { name: /ASR/ })).findByText("Évaluation à venir")).toBeInTheDocument();
    unmount();
    renderApp("/", routes({ asr: 0.125 }));
    expect(await within(await screen.findByRole("article", { name: /ASR/ })).findByText("12,5 %")).toBeInTheDocument();
  });

  it("une valeur absente s'affiche « — », jamais 0", async () => {
    renderApp("/", routes({ blockedActions: null }));
    expect(await within(await screen.findByRole("article", { name: "Actions bloquées" })).findByText("—")).toBeInTheDocument();
  });

  it("état Empty quand aucune requête n'a été analysée", async () => {
    renderApp("/", routes({ totalRequests: 0 }));
    expect(await screen.findByText(/Aucune requête analysée/)).toBeInTheDocument();
  });

  it("état Error avec possibilité de réessayer", async () => {
    let calls = 0;
    renderApp("/", {
      "GET /api/dashboard/overview": () => (++calls === 1 ? { status: 500 } : { body: base }),
      "GET /api/system/health": { body: health },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Impossible de charger");
    await userEvent.click(screen.getByRole("button", { name: "Réessayer" }));
    expect(await screen.findByRole("article", { name: "Requêtes analysées" })).toBeInTheDocument();
  });

  it("les graphiques reflètent les données reçues", async () => {
    renderApp("/", routes());
    const cat = await screen.findByRole("region", { name: "Attaques par catégorie" });
    expect(await within(cat).findByText("Injection indirecte")).toBeInTheDocument();
    expect(within(await screen.findByRole("region", { name: "Répartition des décisions" })).getAllByText(/Bloqué/).length).toBeGreaterThan(0);
  });

  it("un graphique sans donnée affiche un état vide plutôt qu'un graphique vide", async () => {
    renderApp("/", routes({ attacksOverTime: [], byCategory: {} }));
    expect(within(await screen.findByRole("region", { name: "Attaques par catégorie" })).getByText(/Aucune donnée/)).toBeInTheDocument();
  });

  it("l'activité récente renvoie vers le détail de l'événement", async () => {
    renderApp("/", routes());
    const link = await within(await screen.findByRole("list", { name: "Activité récente" })).findByRole("link");
    expect(link).toHaveAttribute("href", "/audit?event=evt-42");
    expect(link).toHaveTextContent("Injection directe bloquée");
  });

  it("un service coupé apparaît comme indisponible ; aucun statut codé en dur", async () => {
    renderApp("/", routes());
    const section = await screen.findByRole("region", { name: "État des services" });
    expect(await within(section).findByText("Indisponible")).toBeInTheDocument();
    expect(within(section).getByText("Disponible")).toBeInTheDocument();
  });

  it("l'état des services est lu sur l'API : tous disponibles si l'API le dit", async () => {
    renderApp("/", routes({}, { services: [{ name: "Service IA", status: "UP" }] }));
    const section = await screen.findByRole("region", { name: "État des services" });
    expect(await within(section).findByText("Disponible")).toBeInTheDocument();
    expect(within(section).queryByText("Indisponible")).not.toBeInTheDocument();
  });
});
