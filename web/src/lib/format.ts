// Cleo — small date/number formatting helpers (mono tabular numerals in CSS).

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '—';
  const s = Math.max(0, (Date.now() - t) / 1000);
  if (s < 60) return 'just now';
  const m = s / 60;
  if (m < 60) return `${Math.floor(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.floor(h)}h ago`;
  const d = h / 24;
  if (d < 30) return `${Math.floor(d)}d ago`;
  return fmtDate(iso);
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '—';
  return new Date(t).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  });
}

/** HH:MM:SS from an ISO string or epoch seconds; falls back to "now". */
export function clock(ts: string | number | null | undefined): string {
  let date: Date;
  if (typeof ts === 'number') date = new Date(ts * 1000);
  else if (typeof ts === 'string' && !Number.isNaN(Date.parse(ts)))
    date = new Date(ts);
  else date = new Date();
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
}

/** "41s" / "3m 41s" between two ISO timestamps; '—' when incomplete. */
export function duration(
  start: string | null | undefined,
  end: string | null | undefined
): string {
  if (!start || !end) return '—';
  const a = Date.parse(start);
  const b = Date.parse(end);
  if (Number.isNaN(a) || Number.isNaN(b) || b < a) return '—';
  const s = Math.round((b - a) / 1000);
  if (s < 60) return `${s}s`;
  return `${Math.floor(s / 60)}m ${s % 60}s`;
}

/** Compact one-line JSON summary for tool args / results. */
export function jsonSummary(value: unknown, max = 180): string {
  let text: string;
  try {
    text = typeof value === 'string' ? value : JSON.stringify(value);
  } catch {
    text = String(value);
  }
  if (!text) return '';
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
