import type { AnalyticsMetrics, AuditPage, AuditQuery, Overview, PolicyView, SessionUser, SystemHealth } from "../types";
import { ApiError, request } from "./http";

export const authService = {
  login: (username: string, password: string) => request<SessionUser>("/api/auth/login", { method: "POST", json: { username, password } }),
  me: (signal?: AbortSignal) => request<SessionUser>("/api/auth/me", {}, signal),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
};

export const dashboardService = {
  overview: async (signal?: AbortSignal) => {
    const data = await request<Overview>("/api/dashboard/overview", {}, signal);
    if (!data || !Array.isArray(data.recent) || !Array.isArray(data.attacksOverTime)
        || ![data.decisions, data.byCategory, data.bySeverity].every(v => v && typeof v === "object" && !Array.isArray(v))) {
      throw new ApiError(502, "Réponse du tableau de bord incompatible");
    }
    return data;
  },
};

export const systemService = {
  health: async (signal?: AbortSignal) => {
    const data = await request<SystemHealth>("/api/system/services", {}, signal);
    if (!Array.isArray(data?.services) || !data.services.every(s => s && typeof s.name === "string" && ["UP", "DOWN", "DEGRADED"].includes(s.status))) {
      throw new ApiError(502, "Réponse de santé incompatible");
    }
    return data;
  },
};

export const auditService = {
  list: (q: AuditQuery, signal?: AbortSignal) => {
    const params = new URLSearchParams({ page: String(q.page), size: String(q.size) });
    if (q.search) params.set("search", q.search);
    if (q.module) params.set("module", q.module);
    if (q.decision) params.set("decision", q.decision);
    return request<AuditPage>(`/api/audit/events?${params.toString()}`, {}, signal);
  },
};

export const policyService = {
  get: (signal?: AbortSignal) => request<PolicyView>("/api/policy", {}, signal),
};

export const analyticsService = {
  metrics: (signal?: AbortSignal) => request<AnalyticsMetrics>("/api/analytics/metrics", {}, signal),
};
