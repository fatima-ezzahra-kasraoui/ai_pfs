/** Formatage d'affichage. Une valeur absente s'affiche « — » : jamais 0 ni une valeur par défaut. */
export const DASH = "—";

export function formatCount(v: number | null | undefined): string {
  return v === null || v === undefined ? DASH : new Intl.NumberFormat("fr-FR").format(v);
}

export function formatPercent(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? DASH : `${(v * 100).toFixed(digits).replace(".", ",")} %`;
}

export function formatNumber(v: number | null | undefined, digits = 3): string {
  return v === null || v === undefined ? DASH : v.toFixed(digits).replace(".", ",");
}

export function formatMs(v: number | null | undefined): string {
  return v === null || v === undefined ? DASH : `${v.toFixed(2).replace(".", ",")} ms`;
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "medium" });
}

export const DECISION_LABEL: Record<string, string> = { ALLOW: "Autorisé", SANITIZE: "Nettoyé", CONFIRM: "À confirmer", BLOCK: "Bloqué" };
export const ATTACK_LABEL: Record<string, string> = {
  direct_injection: "Injection directe",
  indirect_injection: "Injection indirecte",
  data_leak: "Fuite de données",
  tool_abuse: "Abus d'outil",
  none: "Aucune",
};
export const SEVERITY_LABEL: Record<string, string> = { low: "Faible", medium: "Moyenne", high: "Élevée" };
