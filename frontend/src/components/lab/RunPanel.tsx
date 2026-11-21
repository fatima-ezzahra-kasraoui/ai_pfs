import { DASH, formatNumber } from "../../format";
import { cn } from "../../lib/utils";
import { PIPELINE_STEP_NAMES, type PipelineStep, type SimulationRun, type StepStatus, type Verdict } from "../../services/simulation.service";
import { StatusBadge } from "../ui/StatusBadge";

const STEP_LABEL: Record<StepStatus, { label: string; tone: string }> = {
  PENDING: { label: "En attente", tone: "text-muted" },
  RUNNING: { label: "En cours", tone: "text-info" },
  DONE: { label: "Terminé", tone: "text-ok" },
  SKIPPED: { label: "Ignoré", tone: "text-muted" },
  FAILED: { label: "Échec", tone: "text-danger" },
};

/** Le statut d'une étape est toujours porté par un libellé texte, jamais par la couleur seule. */
export function StepStatusBadge({ status }: { status: StepStatus }) {
  const def = STEP_LABEL[status] ?? { label: status, tone: "text-muted" };
  return <span className={cn("inline-flex rounded-full border border-current px-2 py-0.5 text-xs font-medium", def.tone)} data-step-status={status}>{def.label}</span>;
}

/** Score de détection : le plus élevé des scores des verdicts reçus ; `null` s'il n'y en a aucun (jamais 0 par défaut). */
export function detectionScore(steps: PipelineStep[]): number | null {
  const scores = steps.map((s) => s.verdict?.score).filter((v): v is number => typeof v === "number");
  return scores.length ? Math.max(...scores) : null;
}

function VerdictLine({ verdict }: { verdict: Verdict }) {
  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
      <span className="text-muted">Guard {verdict.module}</span>
      {verdict.decision && <StatusBadge status={verdict.decision} />}
      <span aria-label="Score" className="tabular-nums">{formatNumber(verdict.score, 2)}</span>
      {verdict.reason && <span className="basis-full text-xs text-muted">{verdict.reason}</span>}
    </div>
  );
}

function AttackStatus({ run, legitimate }: { run: SimulationRun | null; legitimate: boolean }) {
  if (!run || run.attackSucceeded === null) return <span className="text-muted">{DASH}</span>;
  if (legitimate && !run.attackSucceeded) return <span className="font-semibold text-ok">Aucune attaque (usage légitime)</span>;
  return run.attackSucceeded ? <span className="font-semibold text-danger">Attaque réussie</span> : <span className="font-semibold text-ok">Attaque neutralisée</span>;
}

interface Props {
  title: string;
  /** Exécution reçue du backend (ou du mock) ; `null` tant qu'elle n'est pas disponible. */
  run: SimulationRun | null;
  /** Scénario d'usage légitime : l'absence d'attaque n'est pas une « attaque neutralisée ». */
  legitimate?: boolean;
}

export function RunPanel({ title, run, legitimate = false }: Props) {
  const steps: PipelineStep[] = run?.steps ?? PIPELINE_STEP_NAMES.map((name) => ({ name, status: "PENDING" as const, verdict: null }));
  const score = run ? detectionScore(run.steps) : null;
  return (
    <section aria-label={title} className="min-w-0 rounded-xl border border-line bg-surface p-4">
      <h2 className="m-0 mb-3 text-lg">{title}</h2>

      <h3>Étapes du pipeline</h3>
      <ol aria-label={`Étapes du pipeline : ${title}`} className="m-0 mb-4 list-none p-0">
        {steps.map((step, i) => (
          <li key={`${step.name}-${i}`} className="border-b border-line py-2 last:border-b-0">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-medium"><span className="text-muted">{i + 1}. </span>{step.name}</span>
              <StepStatusBadge status={step.status} />
            </div>
            {step.verdict && <VerdictLine verdict={step.verdict} />}
          </li>
        ))}
      </ol>

      <h3>Résultats</h3>
      <dl aria-label={`Résultats : ${title}`} className="m-0 mb-3">
        <div><dt>Attack Status</dt><dd><AttackStatus run={run} legitimate={legitimate} /></dd></div>
        <div><dt>Detection Score</dt><dd className="tabular-nums">{formatNumber(score, 2)}</dd></div>
        <div><dt>Décision finale</dt><dd>{run?.finalDecision ? <StatusBadge status={run.finalDecision} /> : <span className="text-muted">{DASH}</span>}</dd></div>
      </dl>

      <h3>Réponse finale de l'agent</h3>
      <pre aria-label={`Réponse finale : ${title}`} className="m-0 whitespace-pre-wrap break-words rounded-md border border-line bg-bg p-2 text-sm">{run?.finalResponse || DASH}</pre>
    </section>
  );
}
