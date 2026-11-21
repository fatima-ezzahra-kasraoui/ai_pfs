import { useState } from "react";
import { RunPanel } from "../components/lab/RunPanel";
import { useSimulation } from "../components/lab/useSimulation";
import { StatusBadge } from "../components/ui/StatusBadge";
import { FAMILY_LABEL, SCENARIOS } from "../mocks/scenarios";
import { isMockEnabled } from "../services/simulation.service";

/**
 * Attack Simulation Lab (AS-S1-024). Lance un scénario via `POST /api/simulations/run`, suit `GET /api/simulations/{id}` et affiche
 * l'agent sans puis avec protection, étape par étape. Rien n'est affiché comme « réussi » sans réponse du backend ; tant que le mock
 * est actif (AS-S2-031 le remplacera), le bandeau « Données de démonstration » est visible.
 */
export default function AttackSimulation() {
  const [scenarioId, setScenarioId] = useState(SCENARIOS[0].id);
  const { phase, start } = useSimulation();
  const scenario = SCENARIOS.find((s) => s.id === scenarioId) ?? SCENARIOS[0];
  const running = phase.kind === "running";
  const simulation = phase.kind === "running" || phase.kind === "done" ? phase.simulation : null;
  const failed = phase.kind === "done" && phase.simulation.status === "FAILED";

  return (
    <section className="flex flex-col gap-4">
      <div>
        <h1>Attack Simulation Lab</h1>
        <p className="muted m-0">Rejouez un scénario d'attaque contre l'agent, sans puis avec AgentShield. Outils factices : aucune action réelle.</p>
      </div>

      {isMockEnabled() && (
        <p role="note" className="m-0 rounded-lg border border-warn px-3 py-2 text-sm">
          <strong>Données de démonstration</strong> : les résultats affichés sont simulés localement (mock), pas produits par le backend.
        </p>
      )}

      <form
        aria-label="Choix du scénario"
        className="grid gap-3 rounded-xl border border-line bg-surface p-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (!running) void start(scenarioId);
        }}
      >
        <label className="grid gap-1 font-semibold">
          Scénario
          <select value={scenarioId} onChange={(e) => setScenarioId(e.target.value)} disabled={running} className="w-full max-w-md">
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>{s.title}</option>
            ))}
          </select>
        </label>
        <dl aria-label="Détail du scénario" className="m-0 text-sm">
          <div><dt>Famille</dt><dd>{FAMILY_LABEL[scenario.family]}</dd></div>
          <div><dt>Message envoyé à l'agent</dt><dd>{scenario.userMessage}</dd></div>
          <div><dt>Résultat attendu avec protection</dt><dd>{scenario.expected}</dd></div>
        </dl>
        <div>
          <button type="submit" disabled={running}>{running ? "Simulation en cours…" : "Lancer la simulation"}</button>
        </div>
      </form>

      {phase.kind === "idle" && (
        <p role="status" className="state state-empty m-0">Aucune simulation lancée. Choisissez un scénario puis lancez la simulation.</p>
      )}

      {running && (
        <p role="status" aria-live="polite" className="state state-loading m-0">
          Simulation en cours{simulation ? <> : <StatusBadge status={simulation.status} /></> : "…"}
        </p>
      )}

      {phase.kind === "error" && (
        <div role="alert" className="state state-error">
          <p className="m-0 mb-2">{phase.message}</p>
          <button type="button" onClick={() => void start(scenarioId)}>Réessayer</button>
        </div>
      )}

      {failed && phase.kind === "done" && (
        <div role="alert" className="state state-error">
          <p className="m-0 mb-2">{phase.simulation.error || "La simulation a échoué."}</p>
          <button type="button" onClick={() => void start(scenarioId)}>Réessayer</button>
        </div>
      )}

      {phase.kind === "done" && !failed && (
        <p role="status" className="m-0 flex items-center gap-2 text-sm">Simulation terminée <StatusBadge status={phase.simulation.status} /></p>
      )}

      {phase.kind !== "idle" && phase.kind !== "error" && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <RunPanel title="Unprotected" run={simulation?.unprotected ?? null} legitimate={scenario.family === "normal"} />
          <RunPanel title="Protected" run={simulation?.protected ?? null} legitimate={scenario.family === "normal"} />
        </div>
      )}
    </section>
  );
}
