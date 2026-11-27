import { Activity, TriangleAlert, Ban, Layers, Clock, ChartColumn } from "lucide-react";
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
  const Icon = ({"Requêtes analysées":Activity,"Attaques détectées":TriangleAlert,"Actions bloquées":Ban,"Contenus nettoyés":Layers,"Confirmations en attente":Clock} as Record<string,typeof Activity>)[label] ?? ChartColumn;
  const missing = value === null;
  return (
    <article className="card stat" aria-label={label}>
      <Icon size={21} aria-hidden="true" style={{color:"var(--primary)"}}/><h3>{label}</h3>
      <p className={missing ? "stat-value stat-missing" : "stat-value"}>{missing ? (placeholder ?? DASH) : value}</p>
      {hint && <small>{hint}</small>}
    </article>
  );
}
