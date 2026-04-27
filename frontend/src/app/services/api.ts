/**
 * Central API service layer
 * All requests go to FastAPI backend at localhost:8000 (proxied via Vite dev server)
 */

const BASE_URL = import.meta.env.VITE_API_URL || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// ── Dashboard ─────────────────────────────────────────────────────────
export interface DashboardStats {
  total_episodes: number;
  auto_patch_rate: number;
  mttr_minutes: number;
  pending_review_count: number;
  failure_distribution: Record<string, number>;
  recent_activity: {
    timestamp: string;
    event_type: string;
    description: string;
    entity_id: string;
  }[];
}

export const fetchDashboardStats = (): Promise<DashboardStats> =>
  request('/api/dashboard/stats');

// ── Episodes ──────────────────────────────────────────────────────────
export interface ApiEpisode {
  episode_id: string;
  dag_id: string;
  task_id: string;
  failure_type: string;
  failure_class?: string;
  confidence?: number;
  ml_confidence?: number;
  log_excerpt?: string;
  template?: string;
  status?: string;
  [key: string]: unknown;
}

export const fetchEpisodes = (): Promise<ApiEpisode[]> =>
  request('/api/episodes');

// ── Plans ─────────────────────────────────────────────────────────────
export interface ApiRepairAction {
  operator: string;
  param: string;
  new_value?: string;
  newValue?: string;
  justification?: string;
}

export interface ApiPlan {
  plan_id: string;
  episode_id?: string;
  failure_class: string;
  confidence: number;
  reasoning: string;
  repair_actions: ApiRepairAction[] | string;
  requires_human_approval: boolean;
  status: string;
  fallback_action?: string;
  [key: string]: unknown;
}

export interface PlansResponse {
  plans: ApiPlan[];
  total: number;
}

export const fetchPlans = (params?: { failure_class?: string; status?: string; limit?: number; offset?: number }): Promise<PlansResponse> => {
  const qs = new URLSearchParams();
  if (params?.failure_class) qs.set('failure_class', params.failure_class);
  if (params?.status) qs.set('status', params.status);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  return request(`/api/plans${qs.toString() ? '?' + qs : ''}`);
};

// ── Review Queue ──────────────────────────────────────────────────────
export interface ReviewQueueResponse {
  queue: ApiPlan[];
  total: number;
}

export const fetchReviewQueue = (): Promise<ReviewQueueResponse> =>
  request('/api/review-queue');

export const approvePlan = (planId: string, approvedBy: string, notes = ''): Promise<unknown> =>
  request(`/api/review-queue/${planId}/approve`, {
    method: 'POST',
    body: JSON.stringify({ approved_by: approvedBy, notes }),
  });

export const rejectPlan = (planId: string, rejectedBy: string, reason: string): Promise<unknown> =>
  request(`/api/review-queue/${planId}/reject`, {
    method: 'POST',
    body: JSON.stringify({ rejected_by: rejectedBy, reason }),
  });

// ── Audit ─────────────────────────────────────────────────────────────
export interface ApiAuditEntry {
  plan_id: string;
  episode_id?: string;
  failure_class?: string;
  status: string;
  applied_at: string;
  applied_by?: string;
  rejected_by?: string;
  rejection_reason?: string;
  git_commit_hash?: string;
  dry_run?: boolean;
  notes?: string;
  [key: string]: unknown;
}

export interface AuditResponse {
  entries: ApiAuditEntry[];
  total: number;
}

export const fetchAudit = (params?: { status?: string; limit?: number }): Promise<AuditResponse> => {
  const qs = new URLSearchParams();
  if (params?.status) qs.set('status', params.status);
  if (params?.limit) qs.set('limit', String(params.limit));
  return request(`/api/audit${qs.toString() ? '?' + qs : ''}`);
};

export const exportAudit = () => window.open('/api/audit/export', '_blank');

// ── Rollback ──────────────────────────────────────────────────────────
export interface RollbackEligible {
  rollback_eligible: ApiAuditEntry[];
  total: number;
}

export const fetchRollbackList = (): Promise<RollbackEligible> =>
  request('/api/rollback/list');

export const executeRollback = (planId: string, dryRun = false): Promise<unknown> =>
  request(`/api/rollback/${planId}`, {
    method: 'POST',
    body: JSON.stringify({ dry_run: dryRun }),
  });

// ── Settings ──────────────────────────────────────────────────────────
export interface ThresholdSettings {
  confidence_threshold: number;
  auto_patch_threshold: number;
  require_human_below: number;
  auto_patch_enabled?: boolean;
  dry_run_mode?: boolean;
  audit_logging?: boolean;
}

export const fetchSettings = (): Promise<ThresholdSettings> =>
  request('/api/settings/thresholds');

export const updateSettings = (data: ThresholdSettings): Promise<ThresholdSettings> =>
  request('/api/settings/thresholds', { method: 'PUT', body: JSON.stringify(data) });

export const fetchIntelligence = (): Promise<unknown> =>
  request('/api/intelligence');

// ── A/B Benchmark ─────────────────────────────────────────────────────
export interface BenchmarkMetrics {
  rsr: number;
  mttr_mean: number;
  mttr_std: number;
  frr: number;
  gv: number;
  total: number;
  success_count: number;
  per_class: Record<string, { rsr: number; mttr_mean: number; count: number }>;
}

export interface BenchmarkResponse {
  success: boolean;
  data: {
    selfhealing: BenchmarkMetrics;
    baseline: BenchmarkMetrics;
    deltas: {
      rsr_improvement: number;
      mttr_reduction_pct: number;
      frr_delta: number;
    };
    criteria_met: {
      rsr: boolean;
      mttr_reduction: boolean;
      frr: boolean;
      gv: boolean;
      all_met: boolean;
    };
    total_episodes: number;
    evaluated_at: string;
  };
}

export const fetchBenchmark = (): Promise<BenchmarkResponse> =>
  request('/api/benchmark/run');
