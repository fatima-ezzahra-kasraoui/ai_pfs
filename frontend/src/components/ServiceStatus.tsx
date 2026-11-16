import { systemService } from "../services/api";
import { useAsync } from "../hooks";
import { AsyncView } from "./AsyncView";

const LABEL = { UP: "Disponible", DEGRADED: "Dégradé", DOWN: "Indisponible" } as const;

/** État des services lu sur /api/system/health ; aucun statut codé en dur. */
export function ServiceStatus() {
  const { state, reload } = useAsync((s) => systemService.health(s));
  return (
    <section className="card" aria-label="État des services">
      <h3>État des services</h3>
      <AsyncView state={state} onRetry={reload} isEmpty={(d) => d.services.length === 0} emptyMessage="Aucun service déclaré.">
        {(d) => (
          <ul className="services">
            {d.services.map((s) => (
              <li key={s.name}>
                <span className={`dot dot-${s.status.toLowerCase()}`} aria-hidden="true" />
                <span>{s.name}</span>
                <strong>{LABEL[s.status] ?? s.status}</strong>
                {s.detail && <small>{s.detail}</small>}
              </li>
            ))}
          </ul>
        )}
      </AsyncView>
    </section>
  );
}
