// Cleo — shared UI primitives, faithful to the canonical design language:
// hairline borders, mono tabular numerals, tinted chips, no card-on-card.

import type { ReactNode } from 'react';
import { Icons } from '../lib/icons';
import type { ActionStatus, Sentiment, Source } from '../api';

export type Tone =
  | 'ok'
  | 'warn'
  | 'danger'
  | 'accent'
  | 'violet'
  | 'off'
  | 'none'
  | '';

// ── Dots & chips ──────────────────────────────────────────────

export function Dot({ tone, title }: { tone: Tone; title?: string }) {
  return <span className="dot-tone" data-tone={tone} title={title} />;
}

/** Urgency 0–3 (3 = most urgent); null = untriaged (hollow). */
export function urgencyTone(urgency: number | null | undefined): Tone {
  if (urgency === null || urgency === undefined) return 'none';
  if (urgency >= 3) return 'danger';
  if (urgency === 2) return 'warn';
  if (urgency === 1) return 'accent';
  return 'off';
}

export function UrgencyDot({ urgency }: { urgency: number | null | undefined }) {
  const label =
    urgency === null || urgency === undefined
      ? 'untriaged'
      : `urgency ${urgency}`;
  return <Dot tone={urgencyTone(urgency)} title={label} />;
}

const SOURCE_LETTER: Record<Source, string> = {
  github: 'G',
  intercom: 'I',
  slack: 'S',
  call: 'C',
  doc: 'D',
};

export function SourceTile({
  source,
  size,
}: {
  source: Source | string;
  size?: 'lg';
}) {
  const letter = SOURCE_LETTER[source as Source] ?? '?';
  return (
    <span className="src-tile" data-src={source} data-size={size} title={String(source)}>
      {letter}
    </span>
  );
}

export function TrendChip({ trend }: { trend: string }) {
  const tone: Tone =
    trend === 'rising' ? 'warn' : trend === 'new' ? 'accent' : '';
  return (
    <span className="chip" data-tone={tone || 'outline'}>
      {trend === 'rising' ? (
        <Icons.ArrowUp size={10} />
      ) : trend === 'new' ? (
        <Icons.Sparkle size={10} />
      ) : null}
      {trend}
    </span>
  );
}

export function SentimentChip({ s }: { s: Sentiment | null }) {
  if (!s) return <span className="muted">—</span>;
  const tone: Tone = s === 'pos' ? 'ok' : s === 'neg' ? 'danger' : '';
  const label = s === 'pos' ? 'positive' : s === 'neg' ? 'negative' : 'neutral';
  return (
    <span className="chip" data-tone={tone || 'outline'}>
      {label}
    </span>
  );
}

const ACTION_TONE: Record<ActionStatus, Tone> = {
  proposed: 'accent',
  executed: 'ok',
  failed: 'danger',
  skipped: 'off',
};

export function actionTone(status: string): Tone {
  return ACTION_TONE[status as ActionStatus] ?? '';
}

export function StatusChip({ status }: { status: string }) {
  return (
    <span className="status-chip" data-tone={actionTone(status)}>
      <span className="d" />
      {status}
    </span>
  );
}

export function BetStatusChip({ status }: { status: string }) {
  const tone: Tone =
    status === 'shipped' ? 'ok' : status === 'approved' ? 'violet' : 'accent';
  return (
    <span className="status-chip" data-tone={tone}>
      <span className="d" />
      {status}
    </span>
  );
}

// ── Section header (editorial rule) ───────────────────────────

export function SectionRule({
  num,
  title,
  sub,
  right,
}: {
  num?: string;
  title: string;
  sub?: string;
  right?: ReactNode;
}) {
  return (
    <div className="section-rule">
      {num && <span className="num">{num}</span>}
      <h2>{title}</h2>
      {sub && <span className="sub">{sub}</span>}
      <span className="line" />
      {right}
    </div>
  );
}

// ── Designed states: empty / error / loading ──────────────────

export function EmptyState({
  icon,
  title,
  body,
  hint,
  action,
}: {
  icon: ReactNode;
  title: string;
  body?: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state fade-up">
      <div className="es-ico">{icon}</div>
      <h3 className="es-ttl">{title}</h3>
      {body && <p className="es-bd">{body}</p>}
      {hint && <span className="es-hint">{hint}</span>}
      {action && <div className="es-row">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = 'Could not reach the backend',
  error,
  onRetry,
}: {
  title?: string;
  error: string;
  onRetry?: () => void;
}) {
  return (
    <div className="failcard fade-up">
      <div className="row" style={{ gap: 10, alignItems: 'flex-start' }}>
        <span className="failcard-pip">
          <Icons.X size={10} strokeWidth={2.5} />
        </span>
        <div className="col" style={{ gap: 4, flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13 }}>{title}</div>
          <pre className="failcard-pre">{error}</pre>
        </div>
      </div>
      {onRetry && (
        <div className="row" style={{ gap: 6, marginTop: 10 }}>
          <button className="btn" data-size="sm" onClick={onRetry}>
            <Icons.Refresh size={11} /> Retry
          </button>
        </div>
      )}
    </div>
  );
}

export function Loading({ label = 'Loading' }: { label?: string }) {
  return (
    <div className="loadpane">
      <span className="bar" />
      <span className="lbl">{label}</span>
    </div>
  );
}
