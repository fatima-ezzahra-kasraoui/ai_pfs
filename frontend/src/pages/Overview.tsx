import { AsyncView } from "../components/AsyncView";
import { OverviewCharts } from "../components/OverviewCharts";
import { RecentActivity } from "../components/RecentActivity";
import { ServiceStatus } from "../components/ServiceStatus";
import { StatCard } from "../components/StatCard";
import { formatCount, formatPercent } from "../format";
import { useAsync } from "../hooks";
import { dashboardService } from "../services/api";
import type { Overview as OverviewData } from "../types";

const hasNoActivity = (d: OverviewData) => d.totalRequests === null || d.totalRequests === 0;

export default function Overview() {
  const { state, reload } = useAsync((s) => dashboardService.overview(s));
  return (
    <section>
      <h1>Vue d'ensemble de la sécurité</h1>
      <AsyncView state={state} onRetry={reload} isEmpty={hasNoActivity} emptyMessage="Aucune requête analysée pour l'instant.">
        {(d) => (
          <>
            <div className="grid stats">
              <StatCard label="Requêtes analysées" value={d.totalRequests === null ? null : formatCount(d.totalRequests)} />
              <StatCard label="Attaques détectées" value={d.attacksDetected === null ? null : formatCount(d.attacksDetected)} />
              <StatCard label="Actions bloquées" value={d.blockedActions === null ? null : formatCount(d.blockedActions)} />
              <StatCard label="Contenus nettoyés" value={d.sanitizedActions === null ? null : formatCount(d.sanitizedActions)} />
              <StatCard label="Confirmations en attente" value={d.pendingConfirmations === null ? null : formatCount(d.pendingConfirmations)} />
              <StatCard label="Taux de réussite des attaques (ASR)" value={d.asr === null ? null : formatPercent(d.asr)} placeholder="Évaluation à venir" hint="Mesuré par campagne d'évaluation" />
            </div>
            <OverviewCharts data={d} />
            <section className="card" aria-label="Activité récente">
              <h3>Activité récente</h3>
              <RecentActivity events={d.recent} />
            </section>
          </>
        )}
      </AsyncView>
      <ServiceStatus />
    </section>
  );
}
