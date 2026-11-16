import type { ReactNode } from "react";
import { DASH } from "../../format";
import { cn } from "../../lib/utils";

interface Props {
  label: string;
  /** Valeur déjà formatée ; `null` = non disponible (jamais remplacée par 0). */
  value: string | null;
  /** Texte affiché à la place d'une valeur absente (ex. « Évaluation à venir »). */
  placeholder?: string;
  hint?: string;
  /** Statut associé (ex. <StatusBadge />), toujours accompagné de son libellé. */
  badge?: ReactNode;
  className?: string;
}

export function MetricCard({ label, value, placeholder, hint, badge, className }: Props) {
  const missing = value === null;
  return (
    <article aria-label={label} className={cn("rounded-xl border border-line bg-surface p-4", className)}>
      <div className="flex items-start justify-between gap-2">
        <h3 className="m-0 text-sm font-semibold text-muted">{label}</h3>
        {badge}
      </div>
      <p className={cn("mt-2 mb-0 font-bold", missing ? "text-base text-muted" : "text-2xl")}>{missing ? (placeholder ?? DASH) : value}</p>
      {hint && <small className="text-muted">{hint}</small>}
    </article>
  );
}
