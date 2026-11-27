import { RefreshCw } from "lucide-react";
import { Link } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { OverviewCharts } from "../components/OverviewCharts";
import { RecentActivity } from "../components/RecentActivity";
import { ServiceStatus } from "../components/ServiceStatus";
import { StatCard } from "../components/StatCard";
import { formatCount, formatPercent } from "../format";
import { useAsync } from "../hooks";
import { dashboardService } from "../services/api";
import type { Overview as OverviewData } from "../types";

const hasNoActivity = (d: OverviewData) => d.totalRequests === 0;

export default function Overview() {
  const { state, reload } = useAsync((s) => dashboardService.overview(s));
  return (
    <section className="as-overview">
      <div className="as-title"><div><h1>Security Command Center</h1><p>Supervision et gouvernance des agents IA · Historique disponible</p></div><button type="button" onClick={reload} className="inline-flex items-center gap-2"><RefreshCw size={15} aria-hidden="true"/> Actualiser</button></div>
      <AsyncView state={state} onRetry={reload} isEmpty={hasNoActivity} emptyMessage="Aucune requête analysée pour l'instant.">
        {(d) => (
          <>
            <div className="grid stats">
              <StatCard label="Requêtes analysées" value={d.totalRequests === null ? null : formatCount(d.totalRequests)} />
              <StatCard label="Attaques détectées" hint="Verdicts enregistrés" value={d.attacksDetected === null ? null : formatCount(d.attacksDetected)} />
              <StatCard label="Actions bloquées" hint="Verdicts BLOCK enregistrés" value={d.blockedActions === null ? null : formatCount(d.blockedActions)} />
              <StatCard label="Contenus nettoyés" hint="Verdicts SANITIZE enregistrés" value={d.sanitizedActions === null ? null : formatCount(d.sanitizedActions)} />
              <StatCard label="Confirmations en attente" value={d.pendingConfirmations === null ? null : formatCount(d.pendingConfirmations)} />
              <StatCard label="Taux de réussite des attaques (ASR)" value={d.asr === null ? null : formatPercent(d.asr)} placeholder="Évaluation à venir" hint="Mesuré par campagne d'évaluation" />
            </div>
            <OverviewCharts data={d} />
          </>
        )}
      </AsyncView>

      <div className={state.status === "ready" && !hasNoActivity(state.data) ? "as-bottom" : undefined}>
        {state.status === "ready" && !hasNoActivity(state.data) && (
          <section className="card" aria-label="Activit? r?cente">
            <div className="flex items-center justify-between gap-2">
              <h3>Activit? r?cente</h3>
              <Link to="/audit" className="text-xs">Journal d?audit ?</Link>
            </div>
            <RecentActivity events={state.data.recent} />
          </section>
        )}
        <aside>
          <ServiceStatus />
          {state.status === "ready" && !hasNoActivity(state.data) && (
            <section className="card">
              <h3>Performances des mod?les</h3>
              <p className="muted text-sm">T?l?m?trie non fournie par l?API actuelle.</p>
              <Link to="/analytics" className="text-sm">Consulter les ?valuations</Link>
            </section>
          )}
        </aside>
      </div>
    </section>
  );
}
