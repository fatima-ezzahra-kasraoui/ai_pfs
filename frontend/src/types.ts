/**
 * Types de l'API consommée par l'interface.
 * Contrat PROVISOIRE : à aligner sur l'OpenAPI d'É3 (AS-S1-004). Toute valeur peut être `null`
 * (donnée absente) ; l'interface n'invente jamais de valeur de remplacement.
 */
export type Decision = "ALLOW" | "SANITIZE" | "CONFIRM" | "BLOCK";
export type Severity = "low" | "medium" | "high";
export type AttackType = "direct_injection" | "indirect_injection" | "data_leak" | "tool_abuse" | "none";

export interface SessionUser {
  username: string;
  role: "ADMIN" | "ANALYST" | string;
  email?: string | null;
}

export interface RecentEvent {
  id: string;
  timestamp: string;
  module: string;
  decision: Decision;
  attackType: AttackType;
  summary: string;
}

export interface Overview {
  totalRequests: number | null;
  attacksDetected: number | null;
  blockedActions: number | null;
  sanitizedActions: number | null;
  pendingConfirmations: number | null;
  /** Taux de réussite des attaques : `null` tant qu'aucune campagne n'a été mesurée. */
  asr: number | null;
  attacksOverTime: { date: string; count: number }[];
  decisions: Partial<Record<Decision, number>>;
  byCategory: Partial<Record<AttackType, number>>;
  bySeverity: Partial<Record<Severity, number>>;
  recent: RecentEvent[];
}

export type ServiceState = "UP" | "DOWN" | "DEGRADED";
export interface ServiceHealth {
  name: string;
  status: ServiceState;
  detail?: string | null;
}
export interface SystemHealth {
  services: ServiceHealth[];
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  actor: string;
  action: string;
  module: string;
  decision: Decision | null;
  result: string;
  reference: string;
  details?: Record<string, unknown> | null;
}
export interface AuditPage {
  items: AuditEvent[];
  page: number;
  size: number;
  total: number;
}
export interface AuditQuery {
  search: string;
  module: string;
  decision: string;
  page: number;
  size: number;
}

export interface PolicyView {
  thresholds?: Record<string, number>;
  tools?: Record<string, Record<string, unknown>>;
  output?: Record<string, unknown>;
}

/** Fichier de résultat mesuré (voir ai-service/evaluation/results.schema.json). */
export interface ConfusionMatrix { tp: number; fp: number; tn: number; fn: number }
export interface LatencySummary { n: number; mean: number | null; p50: number | null; p95: number | null; max: number | null }
export interface MeasuredResult {
  name: string;
  kind: "detection" | "benchmark" | "ablation" | "threshold_tuning" | "attack_run";
  split: "validation" | "test";
  status: "preliminary" | "official";
  generatedAt: string;
  commit: string;
  dirty: boolean;
  seed: number;
  config: { agent?: string; simulated?: boolean; configuration?: string; classifier?: string | null } & Record<string, unknown>;
  metrics: {
    asr?: number | null;
    taskSuccess?: number | null;
    nAttacks?: number;
    nNormal?: number;
    perFamily?: Partial<Record<AttackType, { attempted: number; succeeded: number; asr: number | null; recall: number | null }>>;
    detection?: { precision: number | null; recall: number | null; f1: number | null; fpr: number | null; confusion: ConfusionMatrix };
    precision?: number | null;
    recall?: number | null;
    f1?: number | null;
    fpr?: number | null;
    confusion?: ConfusionMatrix;
    latencyMs?: Record<string, LatencySummary> | LatencySummary;
  } & Record<string, unknown>;
  notes?: string[];
}
export interface AnalyticsMetrics {
  status: "ok" | "not_available";
  message?: string | null;
  results: MeasuredResult[];
}
