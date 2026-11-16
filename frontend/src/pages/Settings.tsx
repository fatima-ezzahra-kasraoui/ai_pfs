import { useState } from "react";
import { AsyncView } from "../components/AsyncView";
import { useAsync } from "../hooks";
import { applyTheme, loadTheme, saveTheme, type Theme } from "../preferences";
import { authService, policyService } from "../services/api";

const SECRET_KEY = /key|secret|token|password|passwd|credential|canary/i;

/** Remplace toute valeur dont la clé évoque un secret : la page n'affiche jamais de secret. */
export function redact(value: unknown, key = ""): unknown {
  if (SECRET_KEY.test(key)) return Array.isArray(value) ? `•••• (${value.length} valeur(s) masquée(s))` : "••••";
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, redact(v, k)]));
  return value;
}

function Tree({ data }: { data: unknown }) {
  if (data && typeof data === "object" && !Array.isArray(data)) {
    return (
      <dl>
        {Object.entries(data).map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>
              <Tree data={v} />
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return <>{Array.isArray(data) ? data.map((v) => (typeof v === "object" ? JSON.stringify(v) : String(v))).join(", ") : String(data)}</>;
}

export default function Settings() {
  const me = useAsync((s) => authService.me(s));
  const policy = useAsync((s) => policyService.get(s));
  const [theme, setTheme] = useState<Theme>(loadTheme);

  const onTheme = (t: Theme) => {
    setTheme(t);
    saveTheme(t);
    applyTheme(t);
  };

  return (
    <section>
      <h1>Paramètres</h1>

      <section className="card" aria-label="Profil">
        <h2>Profil</h2>
        <AsyncView state={me.state} onRetry={me.reload}>
          {(u) => (
            <dl>
              <dt>Identifiant</dt>
              <dd>{u.username}</dd>
              <dt>Rôle</dt>
              <dd>{u.role}</dd>
              {u.email && (
                <>
                  <dt>E-mail</dt>
                  <dd>{u.email}</dd>
                </>
              )}
            </dl>
          )}
        </AsyncView>
      </section>

      <section className="card" aria-label="Préférences d'interface">
        <h2>Préférences d'interface</h2>
        <label htmlFor="theme">Thème</label>
        <select id="theme" value={theme} onChange={(e) => onTheme(e.target.value as Theme)}>
          <option value="system">Système</option>
          <option value="light">Clair</option>
          <option value="dark">Sombre</option>
        </select>
      </section>

      <section className="card" aria-label="Plateforme">
        <h2>Plateforme</h2>
        <dl>
          <dt>Application</dt>
          <dd>AgentShield AI</dd>
          <dt>Interface</dt>
          <dd>Lecture seule : les politiques sont définies côté serveur.</dd>
        </dl>
      </section>

      <section className="card" aria-label="Politiques en vigueur">
        <h2>Politiques en vigueur (lecture seule)</h2>
        <AsyncView state={policy.state} onRetry={policy.reload} isEmpty={(p) => Object.keys(p).length === 0} emptyMessage="Aucune politique à afficher.">
          {(p) => <Tree data={redact(p)} />}
        </AsyncView>
      </section>
    </section>
  );
}
