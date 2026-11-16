import { cva, type VariantProps } from "class-variance-authority";
import { CircleAlert, CircleCheck, CircleX, Clock, Eraser, Loader, ShieldAlert, ShieldCheck, ShieldX, type LucideIcon } from "lucide-react";
import { cn } from "../../lib/utils";

/**
 * Pastille de statut. Règle d'accessibilité : l'état n'est JAMAIS porté par la couleur seule —
 * chaque statut affiche un libellé texte (et une icône décorative).
 */
const badge = cva("inline-flex items-center gap-1 rounded-full border border-current px-2 py-0.5 text-xs font-medium", {
  variants: {
    tone: { success: "text-ok", warning: "text-warn", danger: "text-danger", info: "text-info", neutral: "text-muted" },
  },
  defaultVariants: { tone: "neutral" },
});

type Tone = NonNullable<VariantProps<typeof badge>["tone"]>;
interface Def { label: string; tone: Tone; icon: LucideIcon }

/** Décisions du moteur, états des services et statuts de simulation. */
export const STATUS: Record<string, Def> = {
  ALLOW: { label: "Autorisé", tone: "success", icon: ShieldCheck },
  SANITIZE: { label: "Nettoyé", tone: "warning", icon: Eraser },
  CONFIRM: { label: "À confirmer", tone: "info", icon: ShieldAlert },
  BLOCK: { label: "Bloqué", tone: "danger", icon: ShieldX },
  UP: { label: "Opérationnel", tone: "success", icon: CircleCheck },
  DEGRADED: { label: "Dégradé", tone: "warning", icon: CircleAlert },
  DOWN: { label: "Indisponible", tone: "danger", icon: CircleX },
  SUBMITTED: { label: "Soumise", tone: "neutral", icon: Clock },
  RUNNING: { label: "En cours", tone: "info", icon: Loader },
  AWAITING_APPROVAL: { label: "En attente de validation", tone: "warning", icon: Clock },
  COMPLETED: { label: "Terminée", tone: "success", icon: CircleCheck },
  FAILED: { label: "Échec", tone: "danger", icon: CircleX },
};

interface Props {
  /** Code du statut (ex. « BLOCK »). Un code inconnu est affiché tel quel, en neutre. */
  status: string | null | undefined;
  className?: string;
}

export function StatusBadge({ status, className }: Props) {
  const def = status ? STATUS[status.toUpperCase()] : undefined;
  const label = def?.label ?? status ?? "Inconnu";
  const Icon = def?.icon;
  return (
    <span className={cn(badge({ tone: def?.tone ?? "neutral" }), className)} data-status={status ?? "unknown"}>
      {Icon && <Icon aria-hidden="true" size={12} />}
      {label}
    </span>
  );
}
