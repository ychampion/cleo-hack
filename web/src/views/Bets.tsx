// Bets — prioritized product bets: impact / effort / confidence as mono
// numerals, evidence links. Editorial ranked-list composition.

import { useMemo, useState } from 'react';
import { Icons } from '../lib/icons';
import { timeAgo } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import {
  listBets,
  listFeedback,
  listThemes,
  type Bet,
  type Feedback,
  type Theme,
} from '../api';
import {
  BetStatusChip,
  EmptyState,
  ErrorState,
  Loading,
  SourceTile,
  UrgencyDot,
} from '../components/Primitives';
import { Drawer } from '../components/Drawer';

function BetDrawer({
  bet,
  themes,
  onClose,
}: {
  bet: Bet | null;
  themes: Map<string, Theme>;
  onClose: () => void;
}) {
  // §5 has no by-id feedback route — fetch a page and resolve evidence locally.
  const feedback = useFetch<Feedback[]>(
    () => (bet ? listFeedback({ limit: 200 }) : Promise.resolve([])),
    [bet?.id]
  );
  const byId = useMemo(
    () => new Map((feedback.data ?? []).map((f) => [f.id, f])),
    [feedback.data]
  );
  return (
    <Drawer
      open={!!bet}
      onClose={onClose}
      width={520}
      eyebrow={bet ? `bet · ${bet.id}` : undefined}
      title={bet?.title}
    >
      {bet && (
        <div className="col" style={{ gap: 16 }}>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <BetStatusChip status={bet.status} />
            <span className="chip" data-tone="outline">
              <UrgencyDot urgency={bet.urgency} /> urgency {bet.urgency}
            </span>
            <span className="chip" data-tone="outline">
              impact&nbsp;<span className="mono tnum">{bet.impact}</span>
            </span>
            <span className="chip" data-tone="outline">
              effort&nbsp;<span className="mono tnum">{bet.effort}</span>
            </span>
            <span className="chip" data-tone="outline">
              confidence&nbsp;
              <span className="mono tnum">{bet.confidence.toFixed(2)}</span>
            </span>
          </div>

          <div>
            <div className="eyebrow">Problem</div>
            <p style={{ margin: '6px 0 0', fontSize: 13.5, lineHeight: 1.6 }}>{bet.problem}</p>
          </div>
          <div>
            <div className="eyebrow">Proposal</div>
            <p style={{ margin: '6px 0 0', fontSize: 13.5, lineHeight: 1.6 }}>{bet.proposal}</p>
          </div>

          {(bet.theme_ids ?? []).length > 0 && (
            <div>
              <div className="eyebrow">Themes</div>
              <div className="row" style={{ gap: 6, marginTop: 8, flexWrap: 'wrap' }}>
                {bet.theme_ids.map((id) => (
                  <span key={id} className="chip" data-tone="accent">
                    <Icons.Layers size={10} />
                    {themes.get(id)?.title ?? id}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="eyebrow">Evidence</div>
            {feedback.loading ? (
              <Loading label="Resolving evidence" />
            ) : (bet.evidence_ids ?? []).length === 0 ? (
              <p className="muted" style={{ fontSize: 12.5, margin: '6px 0 0' }}>
                No evidence linked.
              </p>
            ) : (
              <div className="col" style={{ gap: 8, marginTop: 8 }}>
                {bet.evidence_ids.map((id) => {
                  const f = byId.get(id);
                  return f ? (
                    <div key={id} className="quote">
                      <div className="qtxt">“{f.text}”</div>
                      <div className="qmeta">
                        <SourceTile source={f.source} />
                        <span className="who">{f.author || f.source}</span>
                        <span>·</span>
                        <span className="mono">{f.id}</span>
                        <span style={{ marginLeft: 'auto' }}>{timeAgo(f.created_at)}</span>
                      </div>
                    </div>
                  ) : (
                    <span key={id} className="chip" data-tone="outline">
                      <Icons.Link size={10} />
                      <span className="mono">{id}</span>
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}
    </Drawer>
  );
}

export function BetsView() {
  const bets = useFetch<Bet[]>(() => listBets(), []);
  const themes = useFetch<Theme[]>(() => listThemes(), []);
  const themeMap = useMemo(
    () => new Map((themes.data ?? []).map((t) => [t.id, t])),
    [themes.data]
  );
  const [selected, setSelected] = useState<Bet | null>(null);

  return (
    <div>
      <div className="page-h">
        <div>
          <h1>Bets</h1>
          <div className="lead">
            Evidence-backed product bets proposed by the agent, ranked for the team to review.
          </div>
        </div>
      </div>
      <div className="page-body">
        {bets.loading ? (
          <Loading label="Loading bets" />
        ) : bets.error ? (
          <ErrorState error={bets.error} onRetry={() => void bets.reload()} />
        ) : (bets.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Icons.Chart size={20} />}
            title="No bets yet"
            body="After triage, the prioritizer proposes bets — each scored for impact, effort, and confidence, with evidence attached."
          />
        ) : (
          <ol className="opp-list">
            {(bets.data ?? []).map((b, i) => (
              <li key={b.id} className="orow" onClick={() => setSelected(b)}>
                <span className="rank">{String(i + 1).padStart(2, '0')}</span>
                <div className="body">
                  <div className="ttl">{b.title}</div>
                  <div className="desc">{b.problem}</div>
                  <div className="meta">
                    <span>
                      impact <b>{b.impact}</b>
                    </span>
                    <span className="sep">·</span>
                    <span>
                      effort <b>{b.effort}</b>
                    </span>
                    <span className="sep">·</span>
                    <span>
                      <b>{(b.evidence_ids ?? []).length}</b> evidence
                    </span>
                    <span className="sep">·</span>
                    <BetStatusChip status={b.status} />
                  </div>
                </div>
                <div className="right">
                  <div className="score-lbl">Confidence</div>
                  <div className="score">{b.confidence.toFixed(2)}</div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
      <BetDrawer bet={selected} themes={themeMap} onClose={() => setSelected(null)} />
    </div>
  );
}
