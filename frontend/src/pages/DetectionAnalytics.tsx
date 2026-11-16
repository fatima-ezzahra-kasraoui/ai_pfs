import { useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AsyncView } from "../components/AsyncView";
import { ATTACK_LABEL, DASH, formatDateTime, formatMs, formatNumber, formatPercent } from "../format";
import { useAsync } from "../hooks";
import { analyticsService } from "../services/api";
import type { ConfusionMatrix, MeasuredResult } from "../types";

const campaignOf = (r: MeasuredResult) => `${r.split}|${r.status}`;
const campaignLabel = (c: string) => {
  const [split, status] = c.split("|");
  return `${split === "test" ? "Test" : "Validation"} (${status === "official" ? "officielle" : "préliminaire"})`;
};
const configOf = (r: MeasuredResult) => String(r.config.configuration ?? r.name);

interface Indicators {
  asr: number | null | undefined;
  precision: number | null | undefined;
  recall: number | null | undefined;
  f1: number | null | undefined;
  fpr: number | null | undefined;
  taskSuccess: number | null | undefined;
  p50: number | null | undefined;
  p95: number | null | undefined;
  confusion: ConfusionMatrix | undefined;
}

/** Lit les indicateurs tels qu'enregistrés dans le fichier de résultats : aucun calcul, aucune valeur par défaut. */
export function indicatorsOf(r: MeasuredResult): Indicators {
  const m = r.metrics;
  const det = m.detection;
  const lat = m.latencyMs && "total" in m.latencyMs ? (m.latencyMs as Record<string, { p50: number | null; p95: number | null }>).total : (m.latencyMs as { p50: number | null; p95: number | null } | undefined);
  return {
    asr: m.asr,
    precision: det?.precision ?? m.precision,
    recall: det?.recall ?? m.recall,
    f1: det?.f1 ?? m.f1,
    fpr: det?.fpr ?? m.fpr,
    taskSuccess: m.taskSuccess,
    p50: lat?.p50,
    p95: lat?.p95,
    confusion: det?.confusion ?? m.confusion,
  };
}

export default function DetectionAnalytics() {
  const { state, reload } = useAsync((s) => analyticsService.metrics(s));
  return (
    <section>
      <h1>Detection Analytics</h1>
      <AsyncView state={state} onRetry={reload}>
        {(d) => (d.status !== "ok" || d.results.length === 0 ? <ComingSoon message={d.message} /> : <Results results={d.results} />)}
      </AsyncView>
    </section>
  );
}

function ComingSoon({ message }: { message?: string | null }) {
  return (
    <div className="card state state-empty" role="status">
      <h2>Évaluation à venir</h2>
      <p>{message ?? "Aucun résultat mesuré n'est disponible."} Les indicateurs s'afficheront ici dès la publication d'une campagne.</p>
    </div>
  );
}

function Results({ results }: { results: MeasuredResult[] }) {
  const campaigns = useMemo(() => [...new Set(results.map(campaignOf))].sort(), [results]);
  // La campagne test, dès qu'elle existe, est présentée en premier sans modifier le code.
  const [campaign, setCampaign] = useState(() => campaigns.find((c) => c.startsWith("test|")) ?? campaigns[0]);
  const inCampaign = results.filter((r) => campaignOf(r) === campaign);
  const configs = [...new Set(inCampaign.map(configOf))];
  const [config, setConfig] = useState("");
  const [attack, setAttack] = useState("");
  const activeConfig = configs.includes(config) ? config : (configs.find((c) => c === "e3") ?? configs[0]);
  const selected = inCampaign.find((r) => configOf(r) === activeConfig) ?? inCampaign[0];
  const simulated = inCampaign.some((r) => r.config.simulated === true);

  return (
    <>
      <form className="filters" aria-label="Filtres">
        <label htmlFor="campaign">Campagne</label>
        <select id="campaign" value={campaign} onChange={(e) => setCampaign(e.target.value)}>
          {campaigns.map((c) => (
            <option key={c} value={c}>
              {campaignLabel(c)}
            </option>
          ))}
        </select>
        <label htmlFor="config">Configuration</label>
        <select id="config" value={activeConfig} onChange={(e) => setConfig(e.target.value)}>
          {configs.map((c) => (
            <option key={c} value={c}>
              {c.toUpperCase()}
            </option>
          ))}
        </select>
        <label htmlFor="attack">Type d'attaque</label>
        <select id="attack" value={attack} onChange={(e) => setAttack(e.target.value)}>
          <option value="">Tous</option>
          {Object.entries(ATTACK_LABEL).filter(([k]) => k !== "none").map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </form>

      {simulated && (
        <p role="note" className="card warning">
          <strong>Agent simulé.</strong> Ces résultats proviennent d'un agent sans modèle de langage : ils mesurent la couverture des protections, pas le taux de réussite d'attaques sur un agent réel.
        </p>
      )}
      {campaign.endsWith("preliminary") && <p className="muted">Campagne préliminaire : mesures de validation, seuils non gelés.</p>}

      {selected && <IndicatorPanel result={selected} attack={attack} />}
      <Comparison results={inCampaign} />
      <Provenance results={inCampaign} />
    </>
  );
}

function IndicatorPanel({ result, attack }: { result: MeasuredResult; attack: string }) {
  const ind = indicatorsOf(result);
  const fam = result.metrics.perFamily ?? {};
  const rows = Object.entries(fam).filter(([k]) => !attack || k === attack);
  const filtered = attack && fam[attack as keyof typeof fam];
  const cells: [string, string][] = filtered
    ? [
        ["ASR", formatPercent(filtered.asr)],
        ["Rappel", formatPercent(filtered.recall)],
        ["Attaques", String(filtered.attempted)],
      ]
    : [
        ["ASR", formatPercent(ind.asr)],
        ["Précision", formatNumber(ind.precision)],
        ["Rappel", formatNumber(ind.recall)],
        ["F1", formatNumber(ind.f1)],
        ["FPR", formatNumber(ind.fpr)],
        ["Task success", formatPercent(ind.taskSuccess)],
        ["Latence p50", formatMs(ind.p50)],
        ["Latence p95", formatMs(ind.p95)],
      ];
  return (
    <section className="card" aria-label="Indicateurs">
      <h2>Indicateurs — {configOf(result).toUpperCase()}</h2>
      <div className="grid stats">
        {cells.map(([k, v]) => (
          <article key={k} className="stat" aria-label={k}>
            <h3>{k}</h3>
            <p className="stat-value">{v}</p>
          </article>
        ))}
      </div>
      {rows.length > 0 && (
        <table className="table">
          <caption>Répartition par catégorie d'attaque</caption>
          <thead>
            <tr>
              <th scope="col">Catégorie</th>
              <th scope="col">Tentées</th>
              <th scope="col">Réussies</th>
              <th scope="col">ASR</th>
              <th scope="col">Rappel</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(([k, v]) => (
              <tr key={k}>
                <td>{ATTACK_LABEL[k] ?? k}</td>
                <td>{v.attempted}</td>
                <td>{v.succeeded}</td>
                <td>{formatPercent(v.asr)}</td>
                <td>{formatPercent(v.recall)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {!attack && ind.confusion && <Confusion c={ind.confusion} />}
    </section>
  );
}

function Confusion({ c }: { c: ConfusionMatrix }) {
  return (
    <table className="table confusion">
      <caption>Matrice de confusion</caption>
      <thead>
        <tr>
          <th scope="col" />
          <th scope="col">Prédit : attaque</th>
          <th scope="col">Prédit : normal</th>
        </tr>
      </thead>
      <tbody>
        <tr>
          <th scope="row">Réel : attaque</th>
          <td>{c.tp}</td>
          <td>{c.fn}</td>
        </tr>
        <tr>
          <th scope="row">Réel : normal</th>
          <td>{c.fp}</td>
          <td>{c.tn}</td>
        </tr>
      </tbody>
    </table>
  );
}

function Comparison({ results }: { results: MeasuredResult[] }) {
  const data = ["e1", "e2", "e3"].flatMap((name) => {
    const r = results.find((x) => x.name === name);
    return r && typeof r.metrics.asr === "number" ? [{ config: name.toUpperCase(), asr: Number((r.metrics.asr * 100).toFixed(1)) }] : [];
  });
  if (data.length === 0) return null;
  return (
    <section className="card chart" aria-label="Comparaison E1, E2, E3">
      <h2>Comparaison E1 / E2 / E3 (ASR, %)</h2>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="config" />
          <YAxis domain={[0, 100]} />
          <Tooltip />
          <Legend />
          <Bar dataKey="asr" name="ASR (%)" fill="#2563eb" />
        </BarChart>
      </ResponsiveContainer>
      <ul className="sr-only">
        {data.map((d) => (
          <li key={d.config}>
            {d.config} : {d.asr} %
          </li>
        ))}
      </ul>
    </section>
  );
}

function Provenance({ results }: { results: MeasuredResult[] }) {
  return (
    <section className="card" aria-label="Provenance des mesures">
      <h2>Provenance des mesures</h2>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Résultat</th>
            <th scope="col">Date</th>
            <th scope="col">Commit</th>
            <th scope="col">Agent</th>
            <th scope="col">Graine</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r) => (
            <tr key={`${r.name}-${r.generatedAt}`}>
              <td>{r.name}</td>
              <td>{formatDateTime(r.generatedAt)}</td>
              <td>
                <code>{r.commit.slice(0, 8)}</code>
                {r.dirty ? " (modifié)" : ""}
              </td>
              <td>{r.config.agent ?? DASH}</td>
              <td>{r.seed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
