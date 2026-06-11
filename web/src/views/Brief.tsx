// Brief — default view: latest weekly brief (markdown) + overview counts +
// urgent-themes banner + recent autonomous actions. Editorial composition.

import { useNavigate } from 'react-router';
import { Icons } from '../lib/icons';
import { Markdown } from '../lib/markdown';
import { timeAgo, fmtDate } from '../lib/format';
import { useOverview } from '../lib/overview';
import {
  Dot,
  EmptyState,
  ErrorState,
  Loading,
  SectionRule,
  StatusChip,
} from '../components/Primitives';
import type { Action, Overview } from '../api';

function StatCells({ overview }: { overview: Overview }) {
  const c = overview.counts ?? {
    feedback: 0,
    untriaged: 0,
    themes: 0,
    bets: 0,
    actions_executed: 0,
  };
  const cells: Array<[string, number, string]> = [
    ['Feedback', c.feedback ?? 0, 'signals ingested'],
    ['Untriaged', c.untriaged ?? 0, 'awaiting the agent'],
    ['Themes', c.themes ?? 0, 'clusters tracked'],
    ['Bets', c.bets ?? 0, 'proposed'],
    ['Actions', c.actions_executed ?? 0, 'executed autonomously'],
  ];
  return (
    <div className="stat-row" style={{ gridTemplateColumns: 'repeat(5, 1fr)' }}>
      {cells.map(([lbl, val, sub]) => (
        <div key={lbl} className="stat-cell">
          <span className="lbl">{lbl}</span>
          <span className="val">{val}</span>
          <span className="sub">{sub}</span>
        </div>
      ))}
    </div>
  );
}

function UrgentBand({ overview }: { overview: Overview }) {
  const navigate = useNavigate();
  const urgent = overview.urgent ?? [];
  if (!urgent.length) return null;
  return (
    <div className="urgent-band fade-up">
      <div className="hd">
        <Dot tone="danger" />
        Urgent — needs a human decision
      </div>
      <div className="items">
        {urgent.map((t) => (
          <div key={t.id} className="item" onClick={() => navigate('/themes')}>
            <span className="ttl">{t.title}</span>
            <span className="meta">
              {(t.feedback_ids ?? []).length} signals · {t.trend}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function RecentActions({ actions }: { actions: Action[] }) {
  const navigate = useNavigate();
  if (!actions.length) {
    return (
      <p className="muted" style={{ fontSize: 13 }}>
        Nothing in the ledger yet — autonomous actions land here as the agent works.
      </p>
    );
  }
  return (
    <div className="ledger">
      {actions.slice(0, 5).map((a) => (
        <div
          key={a.id}
          className="ledger-row"
          data-tone={a.status === 'executed' ? 'ok' : a.status === 'failed' ? 'danger' : 'accent'}
          onClick={() => navigate('/actions')}
        >
          <div className="ts">
            <b>{timeAgo(a.created_at)}</b>
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
            <div className="note truncate">{a.rationale}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function BriefView() {
  const navigate = useNavigate();
  const { data: overview, error, loading, reload } = useOverview();

  if (loading) return <Loading label="Loading the brief" />;
  if (error)
    return (
      <ErrorState
        error={error}
        onRetry={() => {
          void reload();
        }}
      />
    );
  if (!overview) return null;

  const brief = overview.latest_brief;

  return (
    <div className="brief">
      <header className="brief-head">
        <div className="meta">
          {brief ? (
            <>
              <span>
                Week <b>{brief.week}</b>
              </span>
              <span className="sep">/</span>
              <time>{fmtDate(brief.created_at)}</time>
              <span className="sep">/</span>
              <span>written {timeAgo(brief.created_at)}</span>
            </>
          ) : (
            <span>The weekly brief</span>
          )}
        </div>
        <div className="actions">
          <button
            className="btn"
            data-variant="primary"
            data-size="sm"
            onClick={() => navigate('/agent')}
          >
            <Icons.Sparkle size={13} /> Run triage
          </button>
        </div>
      </header>

      <StatCells overview={overview} />
      <UrgentBand overview={overview} />

      <section style={{ marginTop: 48 }}>
        {brief ? (
          <Markdown text={brief.markdown} />
        ) : (
          <EmptyState
            icon={<Icons.Spec size={20} />}
            title="No brief yet"
            body="When the agent runs, it writes the weekly product brief here — themes, urgent issues, and what to do about them."
            action={
              <button className="btn" data-variant="primary" data-size="sm" onClick={() => navigate('/agent')}>
                <Icons.Play size={12} /> Run the agent
              </button>
            }
          />
        )}
      </section>

      <section>
        <SectionRule
          num="02"
          title="Recent autonomous actions"
          sub="from the ledger"
          right={
            <button className="btn" data-variant="ghost" data-size="sm" onClick={() => navigate('/actions')}>
              Open ledger <Icons.ChevR size={11} />
            </button>
          }
        />
        <RecentActions actions={overview.recent_actions ?? []} />
      </section>
    </div>
  );
}
