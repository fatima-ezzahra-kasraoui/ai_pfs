import type { AnalyticsMetrics, AuditPage, AuditQuery, Overview, PolicyView, SessionUser, SystemHealth } from "../types";
import { request } from "./http";

export const authService = {
  login: (username: string, password: string) => request<SessionUser>("/api/auth/login", { method: "POST", json: { username, password } }),
  me: (signal?: AbortSignal) => request<SessionUser>("/api/auth/me", {}, signal),
  logout: () => request<void>("/api/auth/logout", { method: "POST" }),
};

export const dashboardService = {
  overview: (signal?: AbortSignal) => request<Overview>("/api/dashboard/overview", {}, signal),
};

export const systemService = {
  health: (signal?: AbortSignal) => request<SystemHealth>("/api/system/health", {}, signal),
};

export const auditService = {
  list: (q: AuditQuery, signal?: AbortSignal) => {
    const params = new URLSearchParams({ page: String(q.page), size: String(q.size) });
    if (q.search) params.set("search", q.search);
    if (q.module) params.set("module", q.module);
    if (q.decision) params.set("decision", q.decision);
    return request<AuditPage>(`/api/events?${params.toString()}`, {}, signal);
  },
};

export const policyService = {
  get: (signal?: AbortSignal) => request<PolicyView>("/api/policy", {}, signal),
};

export const analyticsService = {
  metrics: (signal?: AbortSignal) => request<AnalyticsMetrics>("/api/analytics/metrics", {}, signal),
};
