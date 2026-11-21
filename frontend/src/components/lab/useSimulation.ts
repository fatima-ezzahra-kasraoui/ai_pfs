import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "../../services/http";
import { MAX_POLLS, pollIntervalMs, simulationService, type Simulation } from "../../services/simulation.service";

export type Phase =
  | { kind: "idle" }
  | { kind: "running"; simulation: Simulation | null }
  | { kind: "done"; simulation: Simulation }
  | { kind: "error"; message: string };

export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 400) return "Scénario refusé par le backend (identifiant inconnu).";
    if (e.status === 401 || e.status === 403) return "Session expirée ou droits insuffisants pour lancer une simulation.";
    if (e.status === 404) return "Simulation introuvable.";
    return "Le backend ou le service IA est indisponible.";
  }
  return "Service injoignable.";
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Aborted", "AbortError"));
    }, { once: true });
  });
}

/**
 * Lance une simulation puis interroge `GET /api/simulations/{id}` jusqu'à un état terminal (COMPLETED, FAILED).
 * Toute donnée affichée provient d'une réponse : aucun résultat n'est déduit côté client. Le polling est annulé au démontage
 * et à chaque nouveau lancement ; il est borné (`MAX_POLLS`).
 */
export function useSimulation() {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const start = useCallback(async (scenarioId: string) => {
    controller.current?.abort();
    const ctl = new AbortController();
    controller.current = ctl;
    setPhase({ kind: "running", simulation: null });
    try {
      const accepted = await simulationService.run(scenarioId, ctl.signal);
      for (let i = 0; i < MAX_POLLS; i++) {
        const simulation = await simulationService.get(accepted.simulationId, ctl.signal);
        if (ctl.signal.aborted) return;
        if (simulation.status === "COMPLETED" || simulation.status === "FAILED") {
          setPhase({ kind: "done", simulation });
          return;
        }
        setPhase({ kind: "running", simulation });
        await sleep(pollIntervalMs(), ctl.signal);
      }
      setPhase({ kind: "error", message: "Délai dépassé : la simulation n'est pas terminée." });
    } catch (e) {
      if (!ctl.signal.aborted) setPhase({ kind: "error", message: describeError(e) });
    }
  }, []);

  return { phase, start };
}
