import { act, cleanup, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { StepStatusBadge, detectionScore } from "../components/lab/RunPanel";
import { mockSimulationBackend } from "../mocks/simulation.mock";
import { SCENARIOS } from "../mocks/scenarios";
import { ApiError } from "../services/http";
import type { PipelineStep, Simulation, SimulationRun, Verdict } from "../services/simulation.service";
import { renderApp, type ApiMock } from "../test/utils";

const verdict = (over: Partial<Verdict> = {}): Verdict => ({ module: "A", attackType: "direct_injection", score: 0.97, riskLevel: "high", decision: "BLOCK", reason: "règle déclenchée", ...over });
const steps = (status: PipelineStep["status"] = "DONE", v: Verdict | null = null): PipelineStep[] =>
  ["Message utilisateur", "Décision de l'agent", "Appel d'outil", "Résultat d'outil", "Moteur de décision", "Réponse finale"].map((name, i) => ({ name, status, verdict: i === 0 ? v : null }));
const run = (mode: SimulationRun["mode"], over: Partial<SimulationRun> = {}): SimulationRun => ({ mode, steps: steps(), finalDecision: null, attackSucceeded: false, finalResponse: "réponse", ...over });
const sim = (status: Simulation["status"], over: Partial<Simulation> = {}): Simulation => ({ simulationId: "sim-1", scenarioId: "scenario-1", status, createdAt: "2026-01-01T00:00:00Z", unprotected: null, protected: null, ...over });

const GET = "GET /api/simulations/sim-1";
const RUN = "POST /api/simulations/run";
const accepted = { simulationId: "sim-1", status: "SUBMITTED" };
const simulationCalls = (api: ApiMock) => api.calls.filter((c) => c.url.includes("/api/simulations"));
const launch = async () => userEvent.click(await screen.findByRole("button", { name: "Lancer la simulation" }));

beforeEach(() => {
  vi.stubEnv("VITE_SIMULATION_POLL_MS", "5");
  mockSimulationBackend.reset();
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
});
const realMode = () => vi.stubEnv("VITE_SIMULATION_MOCK", "false");

describe("intégration au layout de Houda", () => {
  it("s'affiche dans MainLayout via la route /lab existante, avec le lien de navigation actif", async () => {
    renderApp("/lab", {});
    expect(await screen.findByRole("heading", { level: 1, name: "Attack Simulation Lab" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: /principale/i });
    expect(within(nav).getByRole("link", { name: "Attack Simulation Lab" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("banner")).toBeInTheDocument(); // Header du layout
  });

  it("conserve la navigation : on quitte le Lab pour une autre page du layout et on y revient", async () => {
    renderApp("/lab", {});
    const nav = await screen.findByRole("navigation", { name: /principale/i });
    await userEvent.click(within(nav).getByRole("link", { name: "Threat Monitoring" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Threat Monitoring" })).toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("navigation", { name: /principale/i })).getByRole("link", { name: "Attack Simulation Lab" }));
    expect(await screen.findByRole("heading", { level: 1, name: "Attack Simulation Lab" })).toBeInTheDocument();
  });
});

describe("état initial (Empty)", () => {
  it("propose les 5 scénarios, le détail du scénario et aucun résultat", async () => {
    const { api } = renderApp("/lab", {});
    const select = await screen.findByLabelText("Scénario");
    expect(within(select).getAllByRole("option")).toHaveLength(5);
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual(SCENARIOS.map((s) => s.title));
    expect(screen.getByRole("status")).toHaveTextContent("Aucune simulation lancée");
    expect(screen.queryByRole("region", { name: "Unprotected" })).not.toBeInTheDocument();
    expect(simulationCalls(api)).toHaveLength(0);
  });

  it("met à jour le détail quand on change de scénario", async () => {
    renderApp("/lab", {});
    await userEvent.selectOptions(await screen.findByLabelText("Scénario"), "scenario-4");
    const detail = screen.getByLabelText("Détail du scénario");
    expect(detail).toHaveTextContent("Abus d'outil");
    expect(detail).toHaveTextContent("rapport_final.docx");
    expect(detail).toHaveTextContent("delete_file en attente");
  });
});

describe("mode mock : bandeau « Données de démonstration »", () => {
  it("affiche le bandeau et n'appelle jamais le backend", async () => {
    const { api } = renderApp("/lab", {});
    expect(await screen.findByRole("note")).toHaveTextContent("Données de démonstration");
    await launch();
    await screen.findByText("Simulation terminée");
    expect(simulationCalls(api)).toHaveLength(0);
  });

  it("scénario 1 : sans protection l'attaque réussit, avec protection elle est bloquée par le Guard A", async () => {
    renderApp("/lab", {});
    await launch();
    const without = await screen.findByRole("region", { name: "Unprotected" });
    const withShield = screen.getByRole("region", { name: "Protected" });
    await waitFor(() => expect(within(without).getByText("Attaque réussie")).toBeInTheDocument());
    await waitFor(() => expect(within(withShield).getByText("Attaque neutralisée")).toBeInTheDocument());
    expect(within(withShield).getAllByText("Bloqué").length).toBeGreaterThan(0);
    expect(within(withShield).getByText("Guard A")).toBeInTheDocument();
    expect(within(withShield).getByText("Guard ENGINE")).toBeInTheDocument(); // le moteur de décision est une étape exécutée
    const scores = within(withShield).getAllByLabelText("Score");
    expect(scores).toHaveLength(2); // Guard A et verdict ENGINE
    scores.forEach((el) => expect(el).toHaveTextContent(/^\d,\d{2}$/));
    expect(within(without).getByText("Detection Score").nextElementSibling).toHaveTextContent("—"); // aucun guard : pas de score
  });

  it("affiche les six étapes du pipeline dans chaque panneau, avec leur état", async () => {
    renderApp("/lab", {});
    await launch();
    await screen.findByText("Simulation terminée");
    for (const title of ["Unprotected", "Protected"]) {
      const list = screen.getByRole("list", { name: `Étapes du pipeline : ${title}` });
      expect(within(list).getAllByRole("listitem")).toHaveLength(6);
    }
    const protectedList = screen.getByRole("list", { name: "Étapes du pipeline : Protected" });
    expect(within(protectedList).getAllByText("Ignoré").length).toBeGreaterThan(0); // moteur non branché : jamais présenté comme exécuté
  });

  it("scénario 4 : l'action dangereuse est à confirmer côté protégé", async () => {
    renderApp("/lab", {});
    await userEvent.selectOptions(await screen.findByLabelText("Scénario"), "scenario-4");
    await launch();
    const withShield = await screen.findByRole("region", { name: "Protected" });
    await waitFor(() => expect(within(withShield).getAllByText("À confirmer").length).toBeGreaterThan(0));
    expect(within(await screen.findByRole("region", { name: "Unprotected" })).getByText("Attaque réussie")).toBeInTheDocument();
  });

  it("scénario 5 (usage légitime) : autorisé, et jamais présenté comme une attaque neutralisée", async () => {
    renderApp("/lab", {});
    await userEvent.selectOptions(await screen.findByLabelText("Scénario"), "scenario-5");
    await launch();
    const withShield = await screen.findByRole("region", { name: "Protected" });
    await waitFor(() => expect(within(withShield).getByText("Aucune attaque (usage légitime)")).toBeInTheDocument());
    expect(within(withShield).getAllByText("Autorisé").length).toBeGreaterThan(0);
    expect(screen.queryByText("Attaque réussie")).not.toBeInTheDocument();
    expect(screen.queryByText("Attaque neutralisée")).not.toBeInTheDocument();
  });
});

describe("état Loading : aucun statut « réussi » sans réponse", () => {
  it("juste après le lancement : chargement, étapes en attente, aucun résultat d'attaque", async () => {
    realMode();
    renderApp("/lab", { [RUN]: { status: 202, body: accepted }, [GET]: { body: sim("RUNNING", { unprotected: run("unprotected", { steps: steps("PENDING"), attackSucceeded: null }) }) } });
    await launch();
    expect(await screen.findByRole("status")).toHaveTextContent(/Simulation en cours/);
    expect(screen.getByRole("button", { name: "Simulation en cours…" })).toBeDisabled();
    const without = await screen.findByRole("region", { name: "Unprotected" });
    expect(within(without).getAllByText("En attente").length).toBe(6);
    expect(screen.queryByText("Attaque réussie")).not.toBeInTheDocument();
    expect(screen.queryByText("Attaque neutralisée")).not.toBeInTheDocument();
    expect(screen.queryByText("Simulation terminée")).not.toBeInTheDocument();
    expect(within(without).getByText("Attack Status").nextElementSibling).toHaveTextContent("—");
  });
});

describe("mode réel : /api/simulations/*", () => {
  it("lance puis interroge la simulation, sans bandeau, et n'affiche que ce que le backend renvoie", async () => {
    realMode();
    let polls = 0;
    const { api } = renderApp("/lab", {
      [RUN]: { status: 202, body: accepted },
      [GET]: () => {
        polls += 1;
        return polls === 1
          ? { body: sim("RUNNING") }
          : { body: sim("COMPLETED", { completedAt: "2026-01-01T00:00:05Z", unprotected: run("unprotected", { attackSucceeded: true, finalResponse: "RÉPONSE-NON-PROTÉGÉE" }), protected: run("protected", { steps: steps("DONE", verdict()), finalDecision: "BLOCK", finalResponse: "RÉPONSE-PROTÉGÉE" }) }) };
      },
    });
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    await userEvent.selectOptions(await screen.findByLabelText("Scénario"), "scenario-2");
    await launch();
    await screen.findByText("Simulation terminée");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
    const calls = simulationCalls(api);
    expect(calls[0]).toMatchObject({ method: "POST", url: "/api/simulations/run", body: { scenarioId: "scenario-2" } });
    expect(calls.slice(1).every((c) => c.method === "GET" && c.url === "/api/simulations/sim-1")).toBe(true);
    expect(polls).toBe(2);
    expect(screen.getByLabelText("Réponse finale : Unprotected")).toHaveTextContent("RÉPONSE-NON-PROTÉGÉE");
    expect(screen.getByLabelText("Réponse finale : Protected")).toHaveTextContent("RÉPONSE-PROTÉGÉE");
    const withShield = screen.getByRole("region", { name: "Protected" });
    expect(within(withShield).getByText("Detection Score").nextElementSibling).toHaveTextContent("0,97");
    expect(within(screen.getByRole("region", { name: "Unprotected" })).getByText("Attaque réussie")).toBeInTheDocument();
  });

  it("affiche l'état « en attente de validation » puis le résultat", async () => {
    realMode();
    vi.stubEnv("VITE_SIMULATION_POLL_MS", "120"); // laisse l'état intermédiaire visible assez longtemps pour l'observer
    let polls = 0;
    renderApp("/lab", {
      [RUN]: { status: 202, body: accepted },
      [GET]: () => (++polls < 3 ? { body: sim("AWAITING_APPROVAL", { unprotected: run("unprotected") }) } : { body: sim("COMPLETED", { unprotected: run("unprotected"), protected: run("protected", { finalDecision: "CONFIRM" }) }) }),
    });
    await launch();
    expect(await screen.findByText("En attente de validation")).toBeInTheDocument();
    await screen.findByText("Simulation terminée");
    expect(polls).toBe(3);
  });

  it("états d'erreur : refus d'accès, scénario inconnu, service indisponible, réseau coupé", async () => {
    realMode();
    for (const [reply, message] of [
      [{ status: 403 }, /droits insuffisants/],
      [{ status: 400 }, /identifiant inconnu/],
      [{ status: 503 }, /indisponible/],
    ] as const) {
      const { unmount } = renderApp("/lab", { [RUN]: reply });
      await launch();
      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(screen.queryByRole("region", { name: "Unprotected" })).not.toBeInTheDocument();
      unmount();
      vi.restoreAllMocks();
    }
    renderApp("/lab", { [RUN]: () => { throw new TypeError("network"); } });
    await launch();
    expect(await screen.findByRole("alert")).toHaveTextContent("Service injoignable");
  });

  it("erreur pendant le suivi : message, aucun résultat, et « Réessayer » relance une simulation", async () => {
    realMode();
    let runs = 0;
    const { api } = renderApp("/lab", { [RUN]: () => (++runs, { status: 202, body: accepted }), [GET]: { status: 503 } });
    await launch();
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("indisponible");
    expect(screen.queryByText("Simulation terminée")).not.toBeInTheDocument();
    await userEvent.click(within(alert).getByRole("button", { name: "Réessayer" }));
    await waitFor(() => expect(runs).toBe(2));
    expect(simulationCalls(api).filter((c) => c.method === "POST")).toHaveLength(2);
  });

  it("statut FAILED : message générique du backend, sans résultat de réussite", async () => {
    realMode();
    renderApp("/lab", { [RUN]: { status: 202, body: accepted }, [GET]: { body: sim("FAILED", { error: "Service IA indisponible." }) } });
    await launch();
    expect(await screen.findByRole("alert")).toHaveTextContent("Service IA indisponible.");
    expect(screen.queryByText("Simulation terminée")).not.toBeInTheDocument();
    expect(screen.queryByText("Attaque réussie")).not.toBeInTheDocument();
  });

  it("délai dépassé si la simulation ne se termine jamais (polling borné)", async () => {
    realMode();
    vi.stubEnv("VITE_SIMULATION_POLL_MS", "1");
    renderApp("/lab", { [RUN]: { status: 202, body: accepted }, [GET]: { body: sim("RUNNING") } });
    await launch();
    expect(await screen.findByRole("alert", undefined, { timeout: 5000 })).toHaveTextContent("Délai dépassé");
  }, 10000);

  it("arrête le polling au démontage de la page", async () => {
    realMode();
    const { api, unmount } = renderApp("/lab", { [RUN]: { status: 202, body: accepted }, [GET]: { body: sim("RUNNING") } });
    await launch();
    await waitFor(() => expect(simulationCalls(api).length).toBeGreaterThan(1));
    unmount();
    const before = simulationCalls(api).length;
    await act(async () => { await new Promise((r) => setTimeout(r, 60)); });
    expect(simulationCalls(api).length).toBe(before);
  });

  it("n'interprète jamais le HTML renvoyé par l'agent", async () => {
    realMode();
    renderApp("/lab", { [RUN]: { status: 202, body: accepted }, [GET]: { body: sim("COMPLETED", { unprotected: run("unprotected", { finalResponse: "<img src=x onerror=alert(1)><script>window.pwned=1</script>" }), protected: run("protected") }) } });
    await launch();
    expect(await screen.findByLabelText("Réponse finale : Unprotected")).toHaveTextContent("<script>window.pwned=1</script>");
    expect(document.querySelector("main img")).toBeNull();
    expect(document.querySelector("main script")).toBeNull();
  });
});

describe("mock du backend", () => {
  it("reproduit le contrat : SUBMITTED, RUNNING, RUNNING, COMPLETED", async () => {
    const { simulationId, status } = await mockSimulationBackend.run("scenario-1");
    expect(status).toBe("SUBMITTED");
    const seen = [];
    for (let i = 0; i < 3; i++) seen.push(await mockSimulationBackend.get(simulationId));
    expect(seen.map((s) => s.status)).toEqual(["RUNNING", "RUNNING", "COMPLETED"]);
    expect(seen[0].protected).toBeNull();
    expect(seen[1].protected?.attackSucceeded).toBeNull();
    expect(seen[2].completedAt).toBeTruthy();
    expect(seen[2].unprotected?.steps).toHaveLength(6);
  });

  it("refuse un scénario inconnu (400) et une simulation inconnue (404)", async () => {
    await expect(mockSimulationBackend.run("scenario-99")).rejects.toMatchObject({ status: 400 });
    await expect(mockSimulationBackend.get("nope")).rejects.toBeInstanceOf(ApiError);
  });

  it("les 5 scénarios du catalogue ont des fixtures valides pour les deux modes", async () => {
    for (const s of SCENARIOS) {
      const { simulationId } = await mockSimulationBackend.run(s.id);
      await mockSimulationBackend.get(simulationId);
      await mockSimulationBackend.get(simulationId);
      const done = await mockSimulationBackend.get(simulationId);
      expect(done.unprotected?.mode).toBe("unprotected");
      expect(done.protected?.mode).toBe("protected");
      expect(s.id).toMatch(/^[a-z0-9-]{1,40}$/); // motif du contrat public
    }
  });
});

describe("composants", () => {
  it("StepStatusBadge porte l'état par un libellé texte", () => {
    const labels = { PENDING: "En attente", RUNNING: "En cours", DONE: "Terminé", SKIPPED: "Ignoré", FAILED: "Échec" } as const;
    for (const [status, label] of Object.entries(labels)) {
      const { unmount } = renderBadge(status as keyof typeof labels);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });

  it("detectionScore : maximum des scores reçus, null sans verdict (jamais 0 par défaut)", () => {
    expect(detectionScore(steps())).toBeNull();
    expect(detectionScore([{ name: "a", status: "DONE", verdict: verdict({ score: 0.2 }) }, { name: "b", status: "DONE", verdict: verdict({ score: 0.9 }) }])).toBe(0.9);
    expect(detectionScore([{ name: "a", status: "DONE", verdict: verdict({ score: 0 }) }])).toBe(0);
  });
});

import { render } from "@testing-library/react";
function renderBadge(status: PipelineStep["status"]) {
  return render(<StepStatusBadge status={status} />);
}
