// Themes — clustered themes with urgency, trend, evidence count.
// Click a theme → side panel with linked feedback.

import { useState } from 'react';
import { Icons } from '../lib/icons';
import { timeAgo } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import { listFeedback, listThemes, type Feedback, type Theme } from '../api';
import {
  EmptyState,
  ErrorState,
  Loading,
  SourceTile,
  TrendChip,
  UrgencyDot,
} from '../components/Primitives';
import { Drawer } from '../components/Drawer';

function ThemeDrawer({ theme, onClose }: { theme: Theme | null; onClose: () => void }) {
  const evidence = useFetch<Feedback[]>(
    () =>
      theme
        ? listFeedback({ theme_id: theme.id, limit: 100 })
        : Promise.resolve([]),
    [theme?.id]
  );
  return (
    <Drawer
      open={!!theme}
      onClose={onClose}
      width={520}
      eyebrow={theme ? `theme · ${theme.id}` : undefined}
      title={theme?.title}
      subtitle={theme?.summary}
    >
      {theme && (
        <div className="col" style={{ gap: 16 }}>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <span className="chip" data-tone="outline">
              <UrgencyDot urgency={theme.urgency} /> urgency {theme.urgency}
            </span>
            <TrendChip trend={theme.trend} />
            <span className="chip" data-tone="outline">
              <span className="mono tnum">{(theme.feedback_ids ?? []).length}</span>
              &nbsp;signals
            </span>
          </div>
          <div className="kv-grid">
            <span className="k">First seen</span>
            <span className="mono">{timeAgo(theme.first_seen)}</span>
            <span className="k">Last seen</span>
            <span className="mono">{timeAgo(theme.last_seen)}</span>
          </div>

          <div className="eyebrow" style={{ marginTop: 4 }}>
            Linked feedback
          </div>
          {evidence.loading ? (
            <Loading label="Loading evidence" />
          ) : evidence.error ? (
            <ErrorState error={evidence.error} onRetry={() => void evidence.reload()} />
          ) : (evidence.data ?? []).length === 0 ? (
            <p className="muted" style={{ fontSize: 12.5, margin: 0 }}>
              No feedback is linked to this theme yet.
            </p>
          ) : (
            <div className="col" style={{ gap: 8 }}>
              {(evidence.data ?? []).map((f) => (
                <div key={f.id} className="quote">
                  <div className="qtxt">“{f.text}”</div>
                  <div className="qmeta">
                    <SourceTile source={f.source} />
                    <span className="who">{f.author || f.source}</span>
                    <span>·</span>
                    <span className="mono">{f.id}</span>
                    <span style={{ marginLeft: 'auto' }}>{timeAgo(f.created_at)}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </Drawer>
  );
}

export function ThemesView() {
  const themes = useFetch<Theme[]>(() => listThemes(), []);
  const [selected, setSelected] = useState<Theme | null>(null);

  const sorted = [...(themes.data ?? [])].sort(
    (a, b) => (b.urgency ?? 0) - (a.urgency ?? 0)
  );

  return (
    <div>
      <div className="page-h">
        <div>
          <h1>Themes</h1>
          <div className="lead">
            Feedback clustered by the agent — urgency, trend, and the evidence behind each cluster.
          </div>
        </div>
      </div>
      <div className="page-body">
        {themes.loading ? (
          <Loading label="Loading themes" />
        ) : themes.error ? (
          <ErrorState error={themes.error} onRetry={() => void themes.reload()} />
        ) : sorted.length === 0 ? (
          <EmptyState
            icon={<Icons.Layers size={20} />}
            title="No themes yet"
            body="Run triage and the agent will cluster raw feedback into themes, tag urgency, and surface contradictions."
          />
        ) : (
          <div className="theme-list">
            {sorted.map((t) => (
              <div key={t.id} className="theme-row" onClick={() => setSelected(t)}>
                <span className="pip">
                  <UrgencyDot urgency={t.urgency} />
                </span>
                <div>
                  <div className="name">{t.title}</div>
                  <div className="sum">{t.summary}</div>
                  <div className="sub">
                    <span>{t.id}</span>
                    <span>·</span>
                    <span>last seen {timeAgo(t.last_seen)}</span>
                  </div>
                </div>
                <div className="right">
                  <TrendChip trend={t.trend} />
                  <span className="mono tnum" style={{ fontSize: 13, color: 'var(--ink-1)' }}>
                    {(t.feedback_ids ?? []).length}
                  </span>
                  <span className="muted" style={{ fontSize: 11.5 }}>
                    signals
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <ThemeDrawer theme={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
