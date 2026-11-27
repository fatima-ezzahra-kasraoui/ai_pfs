import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ATTACK_LABEL, DECISION_LABEL, SEVERITY_LABEL } from "../format";
import type { Overview } from "../types";

// Palette à contraste suffisant sur fond clair et sombre ; l'information n'est jamais portée par la couleur seule (légende + libellés).
const COLORS = ["#6d4d91", "#a88bc4", "#c7afdd", "#e2d5ee"]
const DECISION_COLORS: Record<string,string> = {ALLOW:"#287D46", SANITIZE:"#74619B", CONFIRM:"#B7791F", BLOCK:"#C24141"};

function entries<K extends string>(obj: Partial<Record<K, number>>, labels: Record<string, string>) {
  return (Object.entries(obj) as [K, number][]).map(([key, value]) => ({ key, name: labels[key] ?? key, value }));
}

function ChartBox({ title, empty, children }: { title: string; empty: boolean; children: React.ReactNode }) {
  return (
    <section className="card chart" aria-label={title}>
      <h3>{title}</h3>
      {empty ? <p className="state state-empty">Aucune donnée pour cette période.</p> : <div className="chart-area">{children}</div>}
    </section>
  );
}

export function OverviewCharts({ data }: { data: Overview }) {
  const decisions = entries(data.decisions, DECISION_LABEL);
  const categories = entries(data.byCategory, ATTACK_LABEL);
  const severities = entries(data.bySeverity, SEVERITY_LABEL);
  return (
    <div className="grid charts">
      <ChartBox title="Attaques dans le temps" empty={data.attacksOverTime.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={data.attacksOverTime}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Area fill="#a88bc4" fillOpacity={0.22} type="monotone" dataKey="count" name="Attaques" stroke={COLORS[0]} strokeWidth={2} dot={false} />
          </AreaChart>
        </ResponsiveContainer>
      </ChartBox>
      <ChartBox title="Répartition des décisions" empty={decisions.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <PieChart>
            <Pie data={decisions} dataKey="value" nameKey="name" innerRadius={48} outerRadius={75}>
              {decisions.map((d, i) => (
                <Cell key={d.key} fill={DECISION_COLORS[d.key] ?? COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Legend />
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </ChartBox>
      <ChartBox title="Attaques par catégorie" empty={categories.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={categories}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" name="Attaques" fill={COLORS[2]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartBox>
      <ChartBox title="Attaques par sévérité" empty={severities.length === 0}>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={severities}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" name="Attaques" fill={COLORS[3]} />
          </BarChart>
        </ResponsiveContainer>
      </ChartBox>
    </div>
  );
}
