import axios, { AxiosError, AxiosResponse } from 'axios';
import { toast } from 'sonner';

// Backend base URL: in Tauri the WebView origin is tauri:// — empty would break.
// Use explicit localhost for desktop; browser keeps same-origin ("").
const __TAURI__ = typeof window !== 'undefined' && '__TAURI__' in window;
const BACKEND_URL: string = __TAURI__
  ? (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000')
  : (import.meta.env.VITE_BACKEND_URL || '');

// Desktop (Tauri) runs in a WebView where cookie domain can mismatch —
 // keep a Bearer token in localStorage as a fallback. Browser users ignore it.
const LS_TOKEN = 'sdg_token_bearer';
export const getStoredToken = (): string | null => {
  try { return localStorage.getItem(LS_TOKEN); } catch { return null; }
};
export const setStoredToken = (t: string | null) => {
  try {
    if (t) localStorage.setItem(LS_TOKEN, t);
    else localStorage.removeItem(LS_TOKEN);
  } catch { /* ignore */ }
};

// Shared axios instance with credentials
export const api = axios.create({
  baseURL: `${BACKEND_URL}/api`,
  withCredentials: true,
});

// Attach Authorization header when we have a stored token (Tauri fallback + future-proofing)
api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token && !config.headers.Authorization) {
    (config.headers as Record<string, string>).Authorization = `Bearer ${token}`;
  }
  return config;
});

// Payload shape for task updates
interface TaskUpdateBody {
  status?: string;
  proof_files?: Record<string, unknown>[];
  assigned_to?: string;
  due_at?: string;
}

// Endpoints for org task management
export const tasksApi = {
  generateWeek: (weekStart?: string) => api.post('/org/tasks/generate-week', { week_start: weekStart }),
  list: (params?: Record<string, unknown>) => api.get('/org/tasks', { params }),
  mine: () => api.get('/org/tasks/mine'),
  update: (id: string, body: TaskUpdateBody) => api.patch(`/org/tasks/${id}`, body),
  review: (id: string) => api.post(`/org/tasks/${id}/ai-review`),
  detectStage: (id: string) => api.post(`/org/tasks/${id}/stage`),
  weeklyDigest: () => api.get('/org/tasks/weekly-digest'),
  departmentHeads: () => api.get('/org/department-heads'),
  setDepartmentHead: (body: Record<string, unknown>) => api.put('/org/department-heads', body),
};

// Global interceptor surfacing backend errors as toasts
api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError<{ detail?: string }>) => {
    const status = error.response?.status;
    const detail = error.response?.data?.detail || '';
    if (status === 402) {
      window.dispatchEvent(new CustomEvent('sdg-insufficient-credits', {
        detail: detail.includes('token limit') ? 'Monthly token limit reached. Top up or wait for your next billing cycle.' : detail || 'Not enough credits.',
      }));
    } else if (!error.response || (status !== undefined && status >= 500 && status < 600)) {
      // Web landing (static GH Pages) has no server → suppress "Could not reach server"
      if (typeof window !== 'undefined' && (import.meta as unknown as Record<string, unknown>)?.env && (import.meta.env as Record<string, string>).VITE_TARGET === 'web') return Promise.reject(error);
      const msg = detail
        || (status !== undefined && status >= 500 ? 'The server had a problem. Please try again.' : 'Could not reach the server. Check your connection.');
      toast.error(msg);
    }
    return Promise.reject(error);
  }
);

// Endpoints for habit tracking
export const habitsApi = {
  list: () => api.get('/v1/habits'),
  create: (body: Record<string, unknown>) => api.post('/v1/habits', body),
  get: (id: string) => api.get(`/v1/habits/${id}`),
  update: (id: string, body: Record<string, unknown>) => api.patch(`/v1/habits/${id}`, body),
  log: (id: string, note?: string) => api.post(`/v1/habits/${id}/log`, { note: note || '' }),
  delete: (id: string) => api.delete(`/v1/habits/${id}`),
};

// Endpoints for playbook workflows
export const playbooksApi = {
  list: () => api.get('/v1/playbooks'),
  available: () => api.get('/v1/playbooks/available'),
  create: (key: string) => api.post('/v1/playbooks', { playbook_key: key }),
  get: (id: string) => api.get(`/v1/playbooks/${id}`),
  update: (id: string, body: Record<string, unknown>) => api.patch(`/v1/playbooks/${id}`, body),
  advance: (id: string) => api.post(`/v1/playbooks/${id}/advance`),
};

// Endpoints for weekly review data
export const weeklyReviewApi = {
  get: () => api.get('/v1/weekly-review'),
  update: (body: Record<string, unknown>) => api.patch('/v1/weekly-review', body),
  reset: () => api.post('/v1/weekly-review/reset'),
  history: () => api.get('/v1/weekly-review/history'),
};

// Severity level used by KPI flags and alerts
type FlagLevel = 'info' | 'warn' | 'crit';

// KPI flag attached to a snapshot metric
interface MetricFlag { key: string; level: FlagLevel; message: string }

// KPI snapshot payload from /metrics/snapshot
interface MetricsSnapshot {
  org_id: string;
  snapshot: {
    cash: number;
    runway_days: number;
    mrr: number;
    churn_pct: number;
    cac: number;
    payback_months: number;
    receivables: number;
    payables: number;
    as_of: string;
    flags: MetricFlag[];
  };
}

// Metric alert record from /metrics/alerts
interface MetricAlert {
  _id: string;
  org_id: string;
  metric: string;
  level: FlagLevel;
  message: string;
  ts: string;
  status: string;
}

// Fetch current KPI snapshot with flags
export const fetchMetricsSnapshot = () => api.get<MetricsSnapshot>('/metrics/snapshot');
// Fetch outstanding metric alerts
export const fetchMetricsAlerts = () => api.get<{ alerts: MetricAlert[] }>('/metrics/alerts');
// Push a single metric value into the ingest pipeline
export const ingestMetric = (body: { name: string; value: number; source?: string }) => api.post<{ ok: boolean }>('/metrics/ingest', body);
// Fetch the latest weekly review with variances
export const fetchWeeklyReview = () => api.get('/loop/weekly-review');
// Run an automation loop (cash | customer | team | all)
export const runAutomationLoop = (loop: 'cash' | 'customer' | 'team' | 'all') => api.post(`/automation/run/${loop}`);
// Fetch automation status and last runs
export const fetchAutomationStatus = () => api.get('/automation/status');
// Fetch governance controls (kill switch, dry run, spend cap)
export const fetchGovernanceStatus = () => api.get('/governance/status');
