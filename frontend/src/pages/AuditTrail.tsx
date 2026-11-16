import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { AsyncView } from "../components/AsyncView";
import { DASH, DECISION_LABEL, formatDateTime } from "../format";
import { useAsync } from "../hooks";
import { auditService } from "../services/api";
import type { AuditEvent, AuditQuery } from "../types";

const PAGE_SIZE = 20;
const MODULES = ["A", "B", "C", "D", "ENGINE"];

/** Journal d'audit : lecture seule. Aucun contrôle de création, de modification ni de suppression. */
export default function AuditTrail() {
  const [params, setParams] = useSearchParams();
  const deepLinked = params.get("event") ?? "";
  const [form, setForm] = useState({ search: deepLinked, module: "", decision: "" });
  const [query, setQuery] = useState<AuditQuery>({ ...form, page: 0, size: PAGE_SIZE });
  const [selected, setSelected] = useState<AuditEvent | null>(null);

  const { state, reload } = useAsync((signal) => auditService.list(query, signal), [query]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setSelected(null);
    setQuery({ ...form, page: 0, size: PAGE_SIZE });
    if (params.has("event")) setParams({}, { replace: true });
  };
  const goto = (page: number) => setQuery((q) => ({ ...q, page }));

  return (
    <section>
      <h1>Journal d'audit</h1>
      <p className="muted">Historique en lecture seule des événements de sécurité.</p>

      <form className="filters" role="search" aria-label="Filtres du journal" onSubmit={submit}>
        <label htmlFor="audit-search">Recherche</label>
        <input id="audit-search" type="search" value={form.search} onChange={(e) => setForm({ ...form, search: e.target.value })} placeholder="Identifiant, action, référence…" />
        <label htmlFor="audit-module">Module</label>
        <select id="audit-module" value={form.module} onChange={(e) => setForm({ ...form, module: e.target.value })}>
          <option value="">Tous</option>
          {MODULES.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <label htmlFor="audit-decision">Décision</label>
        <select id="audit-decision" value={form.decision} onChange={(e) => setForm({ ...form, decision: e.target.value })}>
          <option value="">Toutes</option>
          {Object.entries(DECISION_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button type="submit">Filtrer</button>
      </form>

      <AsyncView state={state} onRetry={reload} isEmpty={(d) => d.items.length === 0} emptyMessage="Aucun événement ne correspond à ces critères.">
        {(page) => (
          <>
            <EventTable events={page.items} selectedId={selected?.id ?? null} onSelect={setSelected} />
            <Pagination page={page.page} size={page.size} total={page.total} onGoto={goto} />
          </>
        )}
      </AsyncView>

      {selected && <EventDetails event={selected} onClose={() => setSelected(null)} />}
    </section>
  );
}

function EventTable({ events, selectedId, onSelect }: { events: AuditEvent[]; selectedId: string | null; onSelect: (e: AuditEvent) => void }) {
  return (
    <table className="table">
      <caption className="sr-only">Événements d'audit</caption>
      <thead>
        <tr>
          <th scope="col">Identifiant</th>
          <th scope="col">Date</th>
          <th scope="col">Utilisateur / agent</th>
          <th scope="col">Action</th>
          <th scope="col">Module</th>
          <th scope="col">Décision</th>
          <th scope="col">Résultat</th>
          <th scope="col">Référence</th>
          <th scope="col">
            <span className="sr-only">Détails</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {events.map((e) => (
          <tr key={e.id} aria-selected={selectedId === e.id}>
            <td>{e.id}</td>
            <td>{formatDateTime(e.timestamp)}</td>
            <td>{e.actor}</td>
            <td>{e.action}</td>
            <td>{e.module}</td>
            <td>{e.decision ? (DECISION_LABEL[e.decision] ?? e.decision) : DASH}</td>
            <td>{e.result}</td>
            <td>{e.reference}</td>
            <td>
              <button type="button" onClick={() => onSelect(e)} aria-label={`Voir les détails de ${e.id}`}>
                Détails
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Pagination({ page, size, total, onGoto }: { page: number; size: number; total: number; onGoto: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" onClick={() => onGoto(page - 1)} disabled={page <= 0}>
        Précédent
      </button>
      <span aria-live="polite">
        Page {page + 1} sur {pages} — {total} événement(s)
      </span>
      <button type="button" onClick={() => onGoto(page + 1)} disabled={page + 1 >= pages}>
        Suivant
      </button>
    </nav>
  );
}

function EventDetails({ event, onClose }: { event: AuditEvent; onClose: () => void }) {
  const rows = useMemo(() => Object.entries(event.details ?? {}), [event]);
  return (
    <aside className="card details" aria-label={`Détails de l'événement ${event.id}`}>
      <h2>Événement {event.id}</h2>
      <dl>
        <dt>Date</dt>
        <dd>{formatDateTime(event.timestamp)}</dd>
        <dt>Utilisateur / agent</dt>
        <dd>{event.actor}</dd>
        <dt>Action</dt>
        <dd>{event.action}</dd>
        <dt>Module</dt>
        <dd>{event.module}</dd>
        <dt>Décision</dt>
        <dd>{event.decision ? (DECISION_LABEL[event.decision] ?? event.decision) : DASH}</dd>
        <dt>Résultat</dt>
        <dd>{event.result}</dd>
        <dt>Référence</dt>
        <dd>{event.reference}</dd>
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            {/* Rendu en texte : un contenu issu d'un agent n'est jamais interprété comme du HTML. */}
            <dd>{typeof v === "string" ? v : JSON.stringify(v)}</dd>
          </div>
        ))}
      </dl>
      <button type="button" onClick={onClose}>
        Fermer
      </button>
    </aside>
  );
}
