// Cleo — typed API client. STRICTLY per CONTRACTS.md §1 (shapes) and §5 (routes).
// Responses are parsed defensively (the backend may wrap lists as {items}/{themes}/…),
// but no endpoints beyond §5 are invented.

// ── §1 data shapes ────────────────────────────────────────────

export type Source = 'github' | 'intercom' | 'slack' | 'call' | 'doc';
export type Sentiment = 'pos' | 'neu' | 'neg';

export interface Feedback {
  id: string;
  source: Source;
  external_id: string;
  author: string;
  text: string;
  url: string | null;
  created_at: string;
  ingested_at: string;
  urgency: number | null; // 0-3 set by agent
  sentiment: Sentiment | null;
  theme_id: string | null;
  metadata: Record<string, unknown>;
}

export interface Theme {
  id: string;
  title: string;
  summary: string;
  urgency: number;
  trend: 'new' | 'rising' | 'steady';
  feedback_ids: string[];
  first_seen: string;
  last_seen: string;
}

export interface Bet {
  id: string;
  title: string;
  problem: string;
  proposal: string;
  impact: number; // 1-5
  effort: number; // 1-5
  confidence: number; // 0.0-1.0
  urgency: number; // 0-3
  theme_ids: string[];
  evidence_ids: string[];
  status: 'proposed' | 'approved' | 'shipped';
  created_at: string;
}

export type ActionType = 'github_issue' | 'github_comment' | 'brief' | 'escalation';
export type ActionStatus = 'proposed' | 'executed' | 'failed' | 'skipped';

export interface Action {
  id: string;
  type: ActionType;
  status: ActionStatus;
  target: string;
  payload: Record<string, unknown>;
  rationale: string;
  evidence_ids: string[];
  created_at: string;
  executed_at: string | null;
  result: Record<string, unknown>;
}

export interface Brief {
  id: string;
  week: string;
  markdown: string;
  theme_ids: string[];
  created_at: string;
}

export interface Directive {
  id: string;
  text: string;
  active: boolean;
  created_at: string;
}

export interface Run {
  id: string;
  trigger: 'manual' | 'loop';
  started_at: string;
  finished_at: string | null;
  status: 'running' | 'done' | 'error';
  summary: string;
  counts: { ingested: number; themes: number; bets: number; actions: number };
}

// §5 GET /api/overview
export interface Overview {
  counts: {
    feedback: number;
    untriaged: number;
    themes: number;
    bets: number;
    actions_executed: number;
  };
  urgent: Theme[];
  latest_brief: Brief | null;
  recent_actions: Action[];
  top_themes: Theme[];
}

// §5 GET /api/runtime/status
export interface RuntimeStatus {
  model: string;
  google_api_key_present: boolean;
  github_token_present: boolean;
  db_path: string;
  feedback_count: number;
}

// ── HTTP helpers ──────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) {
    super(message);
    this.status = status;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError('Backend unreachable — is the API running on :8080?');
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.text();
      if (body) detail += ` — ${body.slice(0, 200)}`;
    } catch {
      /* keep the status line */
    }
    throw new ApiError(detail, res.status);
  }
  const text = await res.text();
  return (text ? JSON.parse(text) : null) as T;
}

/** Accept a bare array or any object wrapping the array ({items}/{themes}/{bets}/…). */
function asList<T>(data: unknown, ...keys: string[]): T[] {
  if (Array.isArray(data)) return data as T[];
  if (data && typeof data === 'object') {
    for (const k of [...keys, 'items']) {
      const v = (data as Record<string, unknown>)[k];
      if (Array.isArray(v)) return v as T[];
    }
  }
  return [];
}

function qs(params: Record<string, string | number | undefined>): string {
  const pairs = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== ''
  );
  if (!pairs.length) return '';
  return (
    '?' +
    pairs.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join('&')
  );
}

// ── §5 routes ─────────────────────────────────────────────────

export function getOverview(): Promise<Overview> {
  return http<Overview>('/api/overview');
}

export async function listFeedback(params: {
  source?: string;
  theme_id?: string;
  urgency?: number;
  limit?: number;
} = {}): Promise<Feedback[]> {
  const data = await http<unknown>(`/api/feedback${qs(params)}`);
  return asList<Feedback>(data, 'feedback');
}

export async function listThemes(): Promise<Theme[]> {
  const data = await http<unknown>('/api/themes');
  return asList<Theme>(data, 'themes');
}

export async function listBets(): Promise<Bet[]> {
  const data = await http<unknown>('/api/bets');
  return asList<Bet>(data, 'bets');
}

export async function listActions(status?: string): Promise<Action[]> {
  const data = await http<unknown>(`/api/actions${qs({ status })}`);
  return asList<Action>(data, 'actions');
}

export async function getLatestBrief(): Promise<Brief | null> {
  const data = await http<unknown>('/api/briefs/latest');
  if (!data || typeof data !== 'object') return null;
  const obj = data as Record<string, unknown>;
  if ('brief' in obj) return (obj.brief as Brief | null) ?? null;
  return 'markdown' in obj ? (data as Brief) : null;
}

export async function listDirectives(): Promise<Directive[]> {
  const data = await http<unknown>('/api/directives');
  return asList<Directive>(data, 'directives');
}

export async function createDirective(text: string): Promise<void> {
  await http<unknown>('/api/directives', {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

export async function setDirectiveActive(
  id: string,
  active: boolean
): Promise<void> {
  await http<unknown>(`/api/directives/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify({ active }),
  });
}

export async function startAgentRun(message?: string): Promise<string | null> {
  const data = await http<unknown>('/api/agent/run', {
    method: 'POST',
    body: JSON.stringify(message ? { message } : {}),
  });
  if (data && typeof data === 'object') {
    const obj = data as Record<string, unknown>;
    const id = obj.run_id ?? obj.id;
    if (typeof id === 'string') return id;
  }
  return null;
}

export async function listRuns(): Promise<Run[]> {
  const data = await http<unknown>('/api/runs');
  return asList<Run>(data, 'runs');
}

export function getRun(id: string): Promise<Run> {
  return http<Run>(`/api/runs/${encodeURIComponent(id)}`);
}

export function getRuntimeStatus(): Promise<RuntimeStatus> {
  return http<RuntimeStatus>('/api/runtime/status');
}

// ── ADK live event stream (POST /run_sse) ─────────────────────
// §5: the UI calls ADK's own /run_sse directly with the session triple that
// /api/agent/run guarantees exists (app "cleo", user "operator", session "ui").
// Lines may be SSE ("data: {…}") or raw JSON — parse defensively.

export interface AdkPart {
  text?: string;
  functionCall?: { name?: string; args?: Record<string, unknown> };
  function_call?: { name?: string; args?: Record<string, unknown> };
  functionResponse?: { name?: string; response?: unknown };
  function_response?: { name?: string; response?: unknown };
  [key: string]: unknown;
}

export interface AdkEvent {
  id?: string;
  author?: string;
  timestamp?: number;
  content?: { role?: string; parts?: AdkPart[] };
  errorMessage?: string;
  error_message?: string;
  /** Set when a stream line was not parseable JSON. */
  raw?: string;
  [key: string]: unknown;
}

export const ADK_SESSION = {
  app_name: 'cleo',
  user_id: 'operator',
  session_id: 'ui',
} as const;

export async function streamRunSse(
  message: string,
  onEvent: (event: AdkEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  let res: Response;
  try {
    res = await fetch('/run_sse', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...ADK_SESSION,
        new_message: { role: 'user', parts: [{ text: message }] },
        streaming: false,
      }),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return;
    throw new ApiError('Live stream unreachable — is the API running on :8080?');
  }
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new ApiError(
      `run_sse ${res.status} ${res.statusText}${body ? ` — ${body.slice(0, 200)}` : ''}`,
      res.status
    );
  }
  if (!res.body) throw new ApiError('run_sse returned no stream body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  const emit = (line: string) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    let payload = trimmed;
    if (payload.startsWith('data:')) payload = payload.slice(5).trim();
    if (!payload || payload === '[DONE]' || payload.startsWith(':')) return;
    try {
      const parsed = JSON.parse(payload) as AdkEvent;
      onEvent(parsed);
    } catch {
      onEvent({ raw: payload });
    }
  };
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let nl = buf.indexOf('\n');
      while (nl >= 0) {
        emit(buf.slice(0, nl));
        buf = buf.slice(nl + 1);
        nl = buf.indexOf('\n');
      }
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') return;
    throw e;
  }
  emit(buf);
}
