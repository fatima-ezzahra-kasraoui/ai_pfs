import { Link } from "react-router-dom";
import { ATTACK_LABEL, DECISION_LABEL, formatDateTime } from "../format";
import type { RecentEvent } from "../types";

/** Activité récente : chaque ligne ouvre le détail de l'événement dans le journal d'audit. */
export function RecentActivity({ events }: { events: RecentEvent[] }) {
  if (events.length === 0) return <p className="state state-empty">Aucune activité récente.</p>;
  return (
    <ul className="recent" aria-label="Activité récente">
      {events.map((e) => (
        <li key={e.id}>
          <Link to={`/audit?event=${encodeURIComponent(e.id)}`}>
            <time dateTime={e.timestamp}>{formatDateTime(e.timestamp)}</time>
            <span className={`badge badge-${e.decision.toLowerCase()}`}>{DECISION_LABEL[e.decision] ?? e.decision}</span>
            <span>
              {e.module} — {ATTACK_LABEL[e.attackType] ?? e.attackType}
            </span>
            <span className="summary">{e.summary}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
