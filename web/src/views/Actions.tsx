// Actions — the autonomous-action ledger. Demo centerpiece: status legible
// at a glance (pip + chip), type, target, rationale, evidence, result.

import { useState } from 'react';
import { Icons } from '../lib/icons';
import { timeAgo, fmtDate } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import {
  listActions,
  listHandoffs,
  type Action,
  type Handoff,
  type HandoffStatus,
} from '../api';
import {
  actionTone,
  EmptyState,
  ErrorState,
  Loading,
  SectionRule,
  StatusChip,
  type Tone,
} from '../components/Primitives';
import { Drawer } from '../components/Drawer';

const STATUSES = ['', 'proposed', 'executed', 'failed', 'skipped'] as const;

const HANDOFF_TONE: Record<HandoffStatus, Tone> = {
  open: 'accent',
  in_progress: 'violet',
  done: 'ok',
  failed: 'danger',
};

function HandoffChip({ status }: { status: string }) {
  return (
    <span className="status-chip" data-tone={HANDOFF_TONE[status as HandoffStatus] ?? ''}>
      <span className="d" />
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function resultLink(a: Action): string | null {
  const r = a.result ?? {};
  for (const key of ['url', 'html_url', 'issue_url', 'link']) {
    const v = (r as Record<string, unknown>)[key];
    if (typeof v === 'string' && v.startsWith('http')) return v;
  }
  return null;
}

function ActionDrawer({ action, onClose }: { action: Action | null; onClose: () => void }) {
  const hasPayload = action && action.payload && Object.keys(action.payload).length > 0;
  const hasResult = action && action.result && Object.keys(action.result).length > 0;
  return (
    <Drawer
      open={!!action}
      onClose={onClose}
      width={520}
      eyebrow={action ? `action · ${action.id}` : undefined}
      title={action ? action.type.replace(/_/g, ' ') : undefined}
      subtitle={action ? `target ${action.target}` : undefined}
    >
      {action && (
        <div className="col" style={{ gap: 16 }}>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <StatusChip status={action.status} />
            <span className="chip" data-tone="outline">
              created {timeAgo(action.created_at)}
            </span>
            {action.executed_at && (
              <span className="chip" data-tone="outline">
                executed {timeAgo(action.executed_at)}
              </span>
            )}
          </div>
          <div>
            <div className="eyebrow">Rationale</div>
            <p style={{ margin: '6px 0 0', fontSize: 13.5, lineHeight: 1.6 }}>
              {action.rationale || '—'}
            </p>
          </div>
          {(action.evidence_ids ?? []).length > 0 && (
            <div>
              <div className="eyebrow">Evidence</div>
              <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {action.evidence_ids.map((id) => (
                  <span key={id} className="chip" data-tone="outline">
                    <Icons.Link size={10} />
                    <span className="mono">{id}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
          {hasPayload && (
            <div>
              <div className="eyebrow">Payload</div>
              <pre className="pre-json" style={{ marginTop: 8 }}>
                {JSON.stringify(action.payload, null, 2)}
              </pre>
            </div>
          )}
          {hasResult && (
            <div>
              <div className="eyebrow">Result</div>
              <pre className="pre-json" style={{ marginTop: 8 }}>
                {JSON.stringify(action.result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

function HandoffsSection() {
  const handoffs = useFetch<Handoff[]>(() => listHandoffs(), []);

  return (
    <>
      <SectionRule num="01" title="Handoffs" sub="bet → coder work orders" />
      {handoffs.loading ? (
        <Loading label="Loading handoffs" />
      ) : handoffs.error ? (
        <ErrorState error={handoffs.error} onRetry={() => void handoffs.reload()} />
      ) : (handoffs.data ?? []).length === 0 ? (
        <p className="muted" style={{ fontSize: 13 }}>
          No handoffs yet — when Cleo dispatches a fix to the coder, the work order
          lands here.
        </p>
      ) : (
        <table className="tbl">
          <thead>
            <tr>
              <th style={{ width: 150 }}>Handoff</th>
              <th>Title</th>
              <th style={{ width: 130 }}>Status</th>
              <th style={{ width: 130 }}>Files changed</th>
              <th style={{ width: 110 }}>Created</th>
            </tr>
          </thead>
          <tbody>
            {(handoffs.data ?? []).map((h) => (
              <tr key={h.id} style={{ cursor: 'default' }}>
                <td className="num" style={{ fontSize: 11.5 }}>
                  {h.id}
                </td>
                <td>{h.title}</td>
                <td>
                  <HandoffChip status={h.status} />
                </td>
                <td className="num">{(h.result?.files_changed ?? []).length}</td>
                <td className="num muted">{timeAgo(h.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

export function ActionsView() {
  const [status, setStatus] = useState<string>('');
  const [selected, setSelected] = useState<Action | null>(null);
  const actions = useFetch<Action[]>(() => listActions(status || undefined), [status]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="page-h" style={{ paddingBottom: 16 }}>
        <div>
          <h1>Actions</h1>
          <div className="lead">
            The autonomous-action ledger — everything Cleo does carries a rationale and
            evidence links, auditable forever.
          </div>
        </div>
        <div className="actions">
          <button className="btn" data-variant="ghost" data-size="sm" onClick={() => void actions.reload()}>
            <Icons.Refresh size={12} /> Refresh
          </button>
        </div>
      </div>
      <div className="filterbar">
        <div className="seg">
          {STATUSES.map((s) => (
            <button key={s || 'all'} data-active={status === s} onClick={() => setStatus(s)}>
              {s === '' ? 'All' : s}
            </button>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        <div className="page-body" style={{ paddingTop: 8 }}>
          <HandoffsSection />
          <SectionRule num="02" title="Ledger" sub="every autonomous action" />
          {actions.loading ? (
            <Loading label="Loading the ledger" />
          ) : actions.error ? (
            <ErrorState error={actions.error} onRetry={() => void actions.reload()} />
          ) : (actions.data ?? []).length === 0 ? (
            <EmptyState
              icon={<Icons.Ledger size={20} />}
              title="The ledger is empty"
              body="When the agent files an issue, writes a brief, or escalates a risk, the action lands here — with status, rationale, and evidence."
            />
          ) : (
            <div className="ledger">
              {(actions.data ?? []).map((a) => {
                const link = resultLink(a);
                return (
                  <div
                    key={a.id}
                    className="ledger-row"
                    data-tone={actionTone(a.status)}
                    onClick={() => setSelected(a)}
                  >
                    <div className="ts">
                      <b>{timeAgo(a.created_at)}</b>
                      {fmtDate(a.created_at)}
                    </div>
                    <div className="pipcol">
                      <span />
                    </div>
                    <div className="body">
                      <div className="head">
                        <StatusChip status={a.status} />
                        <span className="kind-tag">{a.type}</span>
                        <span className="target">{a.target}</span>
                      </div>
                      <div className="note">{a.rationale}</div>
                      <div className="footrow">
                        <span>{(a.evidence_ids ?? []).length} evidence</span>
                        {a.executed_at && <span>executed {timeAgo(a.executed_at)}</span>}
                        {link && (
                          <a
                            href={link}
                            target="_blank"
                            rel="noreferrer"
                            onClick={(e) => e.stopPropagation()}
                          >
                            result <Icons.External size={10} />
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <ActionDrawer action={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
