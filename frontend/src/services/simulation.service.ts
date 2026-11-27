import type { AttackType, Decision } from "../types";
import { mockSimulationBackend } from "../mocks/simulation.mock";
import { request } from "./http";

/**
 * Service des simulations du Lab (AS-S1-024). Contrat : `docs/contract/openapi-public.yaml`
 * (`POST /api/simulations/run`, `GET /api/simulations/{id}`). Types alignés sur ce contrat.
 */
export type GuardModule = "A" | "B" | "C" | "D" | "ENGINE";
export type SimulationStatus = "SUBMITTED" | "RUNNING" | "AWAITING_APPROVAL" | "COMPLETED" | "FAILED";
export type StepStatus = "PENDING" | "RUNNING" | "DONE" | "SKIPPED" | "FAILED";

export interface Verdict {
  module: GuardModule;
  attackType: AttackType;
  score: number;
  riskLevel: "low" | "medium" | "high";
  decision?: Decision | null;
  reason: string;
  correlationId?: string | null;
  cleaned?: string | null;
  degraded?: boolean;
  latencyMs?: number;
  metadata?: Record<string, unknown>;
}
export interface PipelineStep {
  name: string;
  status: StepStatus;
  verdict?: Verdict | null;
}
export interface SimulationRun {
  mode: "unprotected" | "protected";
  steps: PipelineStep[];
  finalDecision?: Decision | null;
  /** `null` tant que l'exécution n'est pas terminée. */
  attackSucceeded: boolean | null;
  finalResponse?: string | null;
}
export interface Simulation {
  simulationId: string;
  scenarioId: string;
  status: SimulationStatus;
  createdAt: string;
  completedAt?: string | null;
  /** Message générique si `status = FAILED` (sans détail interne). */
  error?: string | null;
  unprotected: SimulationRun | null;
  protected: SimulationRun | null;
}
export interface SimulationAccepted {
  simulationId: string;
  status: "SUBMITTED";
}

/**
 * Les six étapes du pipeline, dans l'ordre d'exécution. Les noms réels sont fixés par le backend (Annexe D, à confirmer avec É3) ;
 * cette liste ne sert qu'à afficher des étapes « en attente » avant la première réponse.
 */
export const PIPELINE_STEP_NAMES = ["Message utilisateur", "Décision de l'agent", "Appel d'outil", "Résultat d'outil", "Moteur de décision", "Réponse finale"] as const;

export const MAX_POLLS = 1200;

/**
 * TEMPORARY : le mock est actif tant que `/api/simulations/*` n'est pas branché (AS-S2-031). Il est désactivé en positionnant
 * `VITE_SIMULATION_MOCK=false`. Tant qu'il est actif, la page affiche le bandeau « Données de démonstration » (§16.3).
 */
export const isMockEnabled = (): boolean => import.meta.env.VITE_SIMULATION_MOCK !== "false";
export const pollIntervalMs = (): number => Number(import.meta.env.VITE_SIMULATION_POLL_MS) || 1000;

export const simulationService = {
  run: (scenarioId: string, signal?: AbortSignal): Promise<SimulationAccepted> =>
    isMockEnabled() ? mockSimulationBackend.run(scenarioId) : request<SimulationAccepted>("/api/simulations/run", { method: "POST", json: { scenarioId } }, signal),
  get: (id: string, signal?: AbortSignal): Promise<Simulation> =>
    isMockEnabled() ? mockSimulationBackend.get(id) : request<Simulation>(`/api/simulations/${encodeURIComponent(id)}`, {}, signal),
};
