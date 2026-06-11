// Agent — second demo centerpiece. "Run triage" → POST /api/agent/run, then a
// live event stream from ADK's POST /run_sse rendered as trace rows
// (agent name, tool calls with args summary, text). Run history below.

import { useEffect, useRef, useState } from 'react';
import { Icons } from '../lib/icons';
import { clock, duration, jsonSummary, timeAgo } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import { useOverview } from '../lib/overview';
import {
  listRuns,
  startAgentRun,
  streamRunSse,
  type AdkEvent,
  type Run,
} from '../api';
import {
  Dot,
  EmptyState,
  ErrorState,
  Loading,
  SectionRule,
} from '../components/Primitives';

type RowTone = 'ok' | 'accent' | 'warn' | '';

interface TraceRow {
  key: number;
  t: string;
  tone: RowTone;
  author: string;
  kind: string;
  title: string;
  detail?: string;
}

let rowKey = 0;

/** Defensive: ADK may emit camelCase or snake_case parts; lines may be raw text. */
function eventToRows(ev: AdkEvent): TraceRow[] {
  const t = clock(ev.timestamp ?? null);
  const author = ev.author || 'agent';
  const rows: TraceRow[] = [];

  if (ev.raw !== undefined) {
    rows.push({ key: rowKey++, t, tone: '', author, kind: 'stream', title: ev.raw });
    return rows;
  }
  const err = ev.errorMessage ?? ev.error_message;
  if (typeof err === 'string' && err) {
    rows.push({ key: rowKey++, t, tone: 'warn', author, kind: 'error', title: err });
  }
  for (const p of ev.content?.parts ?? []) {
    const fc = p.functionCall ?? p.function_call;
    const fr = p.functionResponse ?? p.function_response;
    if (fc?.name) {
      rows.push({
        key: rowKey++,
        t,
        tone: 'accent',
        author,
        kind: 'tool call',
        title: fc.name,
        detail: jsonSummary(fc.args ?? {}),
      });
    } else if (fr?.name) {
      rows.push({
        key: rowKey++,
        t,
        tone: 'ok',
        author,
        kind: 'tool result',
        title: fr.name,
        detail: jsonSummary(fr.response ?? {}),
      });
    } else if (typeof p.text === 'string' && p.text.trim()) {
      rows.push({
        key: rowKey++,
        t,
        tone: '',
        author,
        kind: 'said',
        title: p.text.trim(),
      });
    }
  }
  if (!rows.length) {
    rows.push({
      key: rowKey++,
      t,
      tone: '',
      author,
      kind: 'event',
      title: jsonSummary(ev, 140),
    });
  }
  return rows;
}

function runTone(status: Run['status']): RowTone {
  return status === 'done' ? 'ok' : status === 'error' ? 'warn' : 'accent';
}

export function AgentView() {
  const [message, setMessage] = useState('');
  const [rows, setRows] = useState<TraceRow[]>([]);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const paneRef = useRef<HTMLDivElement | null>(null);

  const runs = useFetch<Run[]>(() => listRuns(), []);
  const overview = useOverview();

  // keep the live trace pinned to the latest row
  useEffect(() => {
    const el = paneRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [rows.length]);

  useEffect(() => () => abortRef.current?.abort(), []);

  const start = async () => {
    if (running) return;
    const text = message.trim() || 'Run triage across all feedback sources now.';
    setRows([]);
    setRunError(null);
    setRunning(true);
    abortRef.current = new AbortController();
    try {
      // §5: this guarantees the ADK session (cleo / operator / ui) and opens a
      // run record; the UI then drives ADK's own /run_sse with the same triple.
      await startAgentRun(text);
      await streamRunSse(
        text,
        (ev) => setRows((prev) => [...prev, ...eventToRows(ev)]),
        abortRef.current.signal
      );
    } catch (e) {
      setRunError(e instanceof Error ? e.message : String(e));
    } finally {
      setRunning(false);
      void runs.reload();
      void overview.reload();
    }
  };

  const stop = () => abortRef.current?.abort();

  return (
    <div>
      <div className="page-h">
        <div>
          <h1>Agent</h1>
          <div className="lead">
            Watch Cleo work the pipeline live — ingest → synthesize → prioritize → act.
          </div>
        </div>
        <div className="actions">
          <input
            className="input"
            style={{ width: 280 }}
            placeholder="Optional instruction for this run…"
            value={message}
            disabled={running}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void start();
            }}
          />
          {running ? (
            <button className="btn" data-size="sm" onClick={stop}>
              <Icons.X size={12} /> Stop
            </button>
          ) : (
            <button className="btn" data-variant="primary" onClick={() => void start()}>
              <Icons.Sparkle size={13} /> Run triage
            </button>
          )}
        </div>
      </div>

      <div className="page-body">
        <SectionRule
          num="01"
          title="Live trace"
          sub="streamed from /run_sse"
          right={
            running ? (
              <span className="trace-live">
                <Dot tone="accent" /> <span className="pulse-soft">streaming</span>
              </span>
            ) : undefined
          }
        />
        {runError && <ErrorState title="Run failed" error={runError} onRetry={() => void start()} />}
        {rows.length === 0 && !running && !runError ? (
          <EmptyState
            icon={<Icons.Sparkle size={20} />}
            title="No run in progress"
            body="Press Run triage and every agent step appears here — which sub-agent acted, which MCP tools it called, and what it said."
          />
        ) : (
          <div className="trace-pane" ref={paneRef}>
            <div className="trace-section">
              {rows.map((r) => (
                <div key={r.key} className="trace-row" data-tone={r.tone}>
                  <span className="ts">{r.t}</span>
                  <span className="pip">
                    <span />
                  </span>
                  <div className="body">
                    <div className="who">
                      {r.author}
                      <span className="kind-tag" data-kind={r.kind.startsWith('tool') ? 'tool' : undefined}>
                        {r.kind}
                      </span>
                    </div>
                    <div className="text">{r.title}</div>
                    {r.detail && r.detail !== '{}' && <pre className="args">{r.detail}</pre>}
                  </div>
                </div>
              ))}
              {running && (
                <div className="trace-row" data-tone="accent">
                  <span className="ts">{clock(null)}</span>
                  <span className="pip">
                    <span className="pulse-soft" />
                  </span>
                  <div className="body">
                    <div className="text muted pulse-soft">working…</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        <SectionRule num="02" title="Run history" sub="from the run ledger" />
        {runs.loading ? (
          <Loading label="Loading runs" />
        ) : runs.error ? (
          <ErrorState error={runs.error} onRetry={() => void runs.reload()} />
        ) : (runs.data ?? []).length === 0 ? (
          <p className="muted" style={{ fontSize: 13 }}>
            No runs recorded yet — the first triage run will appear here.
          </p>
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 140 }}>Run</th>
                <th style={{ width: 80 }}>Trigger</th>
                <th style={{ width: 110 }}>Status</th>
                <th style={{ width: 110 }}>Started</th>
                <th style={{ width: 90 }}>Duration</th>
                <th style={{ width: 280 }}>Counts</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {(runs.data ?? []).map((r) => (
                <tr key={r.id} style={{ cursor: 'default' }}>
                  <td className="num" style={{ fontSize: 11.5 }}>
                    {r.id}
                  </td>
                  <td className="muted">{r.trigger}</td>
                  <td>
                    <span className="row" style={{ gap: 6 }}>
                      <Dot tone={runTone(r.status)} />
                      {r.status}
                    </span>
                  </td>
                  <td className="num muted">{timeAgo(r.started_at)}</td>
                  <td className="num muted">{duration(r.started_at, r.finished_at)}</td>
                  <td>
                    <span className="run-counts">
                      <span>
                        <b>{r.counts?.ingested ?? 0}</b> ingested
                      </span>
                      <span>
                        <b>{r.counts?.themes ?? 0}</b> themes
                      </span>
                      <span>
                        <b>{r.counts?.bets ?? 0}</b> bets
                      </span>
                      <span>
                        <b>{r.counts?.actions ?? 0}</b> actions
                      </span>
                    </span>
                  </td>
                  <td className="muted" style={{ maxWidth: 0, width: '100%' }}>
                    <span className="truncate" style={{ display: 'block', maxWidth: '100%' }}>
                      {r.summary || '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
