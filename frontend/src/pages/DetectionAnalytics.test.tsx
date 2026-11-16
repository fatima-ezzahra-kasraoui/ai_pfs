import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp } from "../test/utils";
import type { MeasuredResult } from "../types";
import { indicatorsOf } from "./DetectionAnalytics";

const res = (name: string, over: Partial<MeasuredResult> = {}): MeasuredResult => ({
  name, kind: "benchmark", split: "validation", status: "preliminary", generatedAt: "2026-11-11T10:00:00Z", commit: "abcdef0123456789", dirty: false, seed: 42,
  config: { configuration: name, agent: "sim", simulated: true },
  metrics: {
    asr: name === "e1" ? 0.78 : name === "e2" ? 0.57 : 0.28, taskSuccess: 0.9,
    detection: { precision: 0.91, recall: 0.82, f1: 0.86, fpr: 0.04, confusion: { tp: 41, fp: 3, tn: 70, fn: 9 } },
    latencyMs: { total: { n: 10, mean: 1, p50: 1.5, p95: 3.25, max: 4 } },
    perFamily: { direct_injection: { attempted: 10, succeeded: 3, asr: 0.3, recall: 0.7 } },
  },
  ...over,
});
const ok = (results: MeasuredResult[]) => ({ "GET /api/analytics/metrics": { body: { status: "ok", results } } });

describe("DetectionAnalytics", () => {
  it("sans résultat : « Évaluation à venir », aucun chiffre inventé", async () => {
    renderApp("/analytics", { "GET /api/analytics/metrics": { body: { status: "not_available", message: "Aucun résultat.", results: [] } } });
    expect(await screen.findByText("Évaluation à venir")).toBeInTheDocument();
    expect(screen.getByRole("status").textContent).not.toMatch(/\d/);
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("affiche les indicateurs mesurés, la matrice de confusion et la provenance", async () => {
    renderApp("/analytics", ok([res("e1"), res("e2"), res("e3")]));
    const panel = await screen.findByRole("region", { name: "Indicateurs" });
    const stat = (n: string) => within(within(panel).getByRole("article", { name: n })).getByText(/./, { selector: ".stat-value" });
    expect(stat("ASR")).toHaveTextContent("28,0 %");
    expect(stat("Rappel")).toHaveTextContent("0,820");
    expect(stat("Latence p95")).toHaveTextContent("3,25 ms");
    const confusion = within(panel).getByRole("table", { name: "Matrice de confusion" });
    expect(within(confusion).getByText("41")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Provenance des mesures" })).toHaveTextContent("abcdef01");
    expect(screen.getByRole("region", { name: "Comparaison E1, E2, E3" })).toBeInTheDocument();
  });

  it("signale l'agent simulé et le caractère préliminaire", async () => {
    renderApp("/analytics", ok([res("e3")]));
    expect(await screen.findByRole("note")).toHaveTextContent("Agent simulé");
    expect(screen.getByText(/Campagne préliminaire/)).toBeInTheDocument();
  });

  it("préfère la campagne test officielle dès qu'elle existe", async () => {
    const test = res("e3", { split: "test", status: "official", config: { configuration: "e3", agent: "reel" }, metrics: { asr: 0.1 } });
    renderApp("/analytics", ok([res("e3"), test]));
    const panel = await screen.findByRole("region", { name: "Indicateurs" });
    expect(within(panel).getByRole("article", { name: "ASR" })).toHaveTextContent("10,0 %");
    expect(screen.getByLabelText("Campagne")).toHaveValue("test|official");
    expect(screen.queryByRole("note")).not.toBeInTheDocument();
  });

  it("une valeur null s'affiche « — »", async () => {
    renderApp("/analytics", ok([res("e3", { metrics: { asr: null } })]));
    const panel = await screen.findByRole("region", { name: "Indicateurs" });
    expect(within(panel).getByRole("article", { name: "ASR" })).toHaveTextContent("—");
    expect(within(panel).getByRole("article", { name: "Latence p50" })).toHaveTextContent("—");
  });

  it("le filtre par type d'attaque restreint l'affichage", async () => {
    renderApp("/analytics", ok([res("e3")]));
    await screen.findByRole("region", { name: "Indicateurs" });
    await userEvent.selectOptions(screen.getByLabelText("Type d'attaque"), "direct_injection");
    const panel = screen.getByRole("region", { name: "Indicateurs" });
    expect(within(panel).getByRole("article", { name: "ASR" })).toHaveTextContent("30,0 %");
    expect(within(panel).queryByRole("table", { name: "Matrice de confusion" })).not.toBeInTheDocument();
  });

  it("gère l'erreur serveur", async () => {
    renderApp("/analytics", { "GET /api/analytics/metrics": { status: 500 } });
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });

  it("indicatorsOf lit tel quel, sans valeur par défaut", () => {
    const i = indicatorsOf(res("e3", { metrics: {} }));
    expect(i.asr).toBeUndefined();
    expect(i.recall).toBeUndefined();
    expect(indicatorsOf(res("e3", { metrics: { recall: 0.5, latencyMs: { n: 1, mean: 1, p50: 2, p95: 3, max: 3 } } })).p95).toBe(3);
  });
});
