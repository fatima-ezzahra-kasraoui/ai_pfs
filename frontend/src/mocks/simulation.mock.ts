import { ApiError } from "../services/http";
import type { PipelineStep, Simulation, SimulationAccepted, SimulationRun } from "../services/simulation.service";
import { SCENARIOS } from "./scenarios";
import { SIMULATION_FIXTURES } from "./simulation.fixtures";

/**
 * Faux backend des simulations (TEMPORARY, supprimé avec AS-S2-031). Reproduit le contrat de `/api/simulations/*` :
 * `run` répond « SUBMITTED », puis chaque `get` fait avancer la simulation (RUNNING → COMPLETED). Les résultats viennent des
 * fixtures générées depuis l'agent réel (LLM simulé). Un identifiant inconnu est refusé comme le ferait le backend (400).
 */
interface State {
  scenarioId: string;
  polls: number;
  createdAt: string;
}
const store = new Map<string, State>();
let counter = 0;

const pending = (run: SimulationRun): SimulationRun => ({
  mode: run.mode,
  steps: run.steps.map((s): PipelineStep => ({ name: s.name, status: "PENDING", verdict: null })),
  finalDecision: null,
  attackSucceeded: null,
  finalResponse: null,
});

export const mockSimulationBackend = {
  async run(scenarioId: string): Promise<SimulationAccepted> {
    if (!SCENARIOS.some((s) => s.id === scenarioId) || !(scenarioId in SIMULATION_FIXTURES)) throw new ApiError(400, "HTTP 400");
    const simulationId = `mock-${++counter}`;
    store.set(simulationId, { scenarioId, polls: 0, createdAt: new Date().toISOString() });
    return { simulationId, status: "SUBMITTED" };
  },

  async get(id: string): Promise<Simulation> {
    const state = store.get(id);
    if (!state) throw new ApiError(404, "HTTP 404");
    state.polls += 1;
    const fx = SIMULATION_FIXTURES[state.scenarioId];
    const base = { simulationId: id, scenarioId: state.scenarioId, createdAt: state.createdAt };
    if (state.polls === 1) return { ...base, status: "RUNNING", unprotected: pending(fx.unprotected), protected: null };
    if (state.polls === 2) return { ...base, status: "RUNNING", unprotected: fx.unprotected, protected: pending(fx.protected) };
    return { ...base, status: "COMPLETED", completedAt: new Date().toISOString(), unprotected: fx.unprotected, protected: fx.protected };
  },

  /** Réinitialise l'état (tests). */
  reset(): void {
    store.clear();
    counter = 0;
  },
};
