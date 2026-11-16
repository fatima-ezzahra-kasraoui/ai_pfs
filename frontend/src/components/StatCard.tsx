import { DASH } from "../format";

interface Props {
  label: string;
  /** Valeur déjà formatée ; `null` = non disponible. */
  value: string | null;
  /** Texte affiché à la place d'une valeur absente (ex. « Évaluation à venir »). */
  placeholder?: string;
  hint?: string;
}

export function StatCard({ label, value, placeholder, hint }: Props) {
  const missing = value === null;
  return (
    <article className="card stat" aria-label={label}>
      <h3>{label}</h3>
      <p className={missing ? "stat-value stat-missing" : "stat-value"}>{missing ? (placeholder ?? DASH) : value}</p>
      {hint && <small>{hint}</small>}
    </article>
  );
}
