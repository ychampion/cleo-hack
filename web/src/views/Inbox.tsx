// Inbox — dense feedback table: urgency dots, source chips, filters.

import { useMemo, useState } from 'react';
import { Icons } from '../lib/icons';
import { timeAgo } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import { listFeedback, listThemes, type Feedback, type Theme } from '../api';
import {
  EmptyState,
  ErrorState,
  Loading,
  SentimentChip,
  SourceTile,
  UrgencyDot,
} from '../components/Primitives';
import { Drawer } from '../components/Drawer';

const SOURCES = ['github', 'intercom', 'slack', 'call', 'doc'] as const;

function FeedbackDrawer({
  item,
  themes,
  onClose,
}: {
  item: Feedback | null;
  themes: Map<string, Theme>;
  onClose: () => void;
}) {
  const theme = item?.theme_id ? themes.get(item.theme_id) : undefined;
  const hasMeta = item && item.metadata && Object.keys(item.metadata).length > 0;
  return (
    <Drawer
      open={!!item}
      onClose={onClose}
      eyebrow={item ? `${item.source} · ${item.id}` : undefined}
      title={item?.author || 'Feedback'}
      subtitle={item ? `received ${timeAgo(item.created_at)}` : undefined}
    >
      {item && (
        <div className="col" style={{ gap: 16 }}>
          <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
            <span className="chip" data-tone="outline">
              <UrgencyDot urgency={item.urgency} />
              {item.urgency === null ? 'untriaged' : `urgency ${item.urgency}`}
            </span>
            <SentimentChip s={item.sentiment} />
            {theme && (
              <span className="chip" data-tone="accent">
                <Icons.Layers size={10} /> {theme.title}
              </span>
            )}
          </div>
          <div
            style={{
              fontSize: 14.5,
              lineHeight: 1.6,
              color: 'var(--ink-1)',
              textWrap: 'pretty',
            }}
          >
            “{item.text}”
          </div>
          <div className="kv-grid">
            <span className="k">Source</span>
            <span className="row" style={{ gap: 6 }}>
              <SourceTile source={item.source} /> {item.source}
            </span>
            <span className="k">Author</span>
            <span>{item.author || '—'}</span>
            <span className="k">External id</span>
            <span className="mono">{item.external_id || '—'}</span>
            <span className="k">Created</span>
            <span className="mono">{item.created_at}</span>
            <span className="k">Ingested</span>
            <span className="mono">{item.ingested_at}</span>
            {item.url && (
              <>
                <span className="k">Link</span>
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  className="row"
                  style={{ gap: 4, color: 'var(--accent-ink)' }}
                >
                  open source <Icons.External size={11} />
                </a>
              </>
            )}
          </div>
          {hasMeta && (
            <pre className="pre-json">{JSON.stringify(item.metadata, null, 2)}</pre>
          )}
        </div>
      )}
    </Drawer>
  );
}

export function InboxView() {
  const [filter, setFilter] = useState<'all' | 'untriaged'>('all');
  const [source, setSource] = useState('');
  const [selected, setSelected] = useState<Feedback | null>(null);

  const feedback = useFetch<Feedback[]>(
    () => listFeedback({ source: source || undefined, limit: 200 }),
    [source]
  );
  const themes = useFetch<Theme[]>(() => listThemes(), []);
  const themeMap = useMemo(
    () => new Map((themes.data ?? []).map((t) => [t.id, t])),
    [themes.data]
  );

  // §5 /api/feedback has no untriaged param — filtered client-side (urgency null).
  const rows = useMemo(() => {
    const all = feedback.data ?? [];
    return filter === 'untriaged' ? all.filter((f) => f.urgency === null) : all;
  }, [feedback.data, filter]);

  const untriagedCount = (feedback.data ?? []).filter((f) => f.urgency === null).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
      <div className="filterbar">
        <div className="seg">
          <button data-active={filter === 'all'} onClick={() => setFilter('all')}>
            All
            {feedback.data && <span className="ct">{feedback.data.length}</span>}
          </button>
          <button data-active={filter === 'untriaged'} onClick={() => setFilter('untriaged')}>
            Untriaged
            {feedback.data && <span className="ct">{untriagedCount}</span>}
          </button>
        </div>
        <select className="input" value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="">All sources</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <div style={{ flex: 1, overflow: 'auto', minHeight: 0 }}>
        {feedback.loading ? (
          <Loading label="Loading feedback" />
        ) : feedback.error ? (
          <ErrorState error={feedback.error} onRetry={() => void feedback.reload()} />
        ) : rows.length === 0 ? (
          <EmptyState
            icon={<Icons.Inbox size={20} />}
            title={filter === 'untriaged' ? 'Nothing untriaged' : 'No feedback yet'}
            body={
              filter === 'untriaged'
                ? 'Every signal has been triaged by the agent. New feedback lands here first.'
                : 'Seed the demo corpus, then run the agent to pull feedback from every source.'
            }
            hint={filter === 'all' ? 'uv run python -m seed.seed' : undefined}
          />
        ) : (
          <table className="tbl">
            <thead>
              <tr>
                <th style={{ width: 28 }} title="Urgency"></th>
                <th style={{ width: 28 }} title="Source"></th>
                <th style={{ width: 116 }}>ID</th>
                <th>Message</th>
                <th style={{ width: 130 }}>Author</th>
                <th style={{ width: 160 }}>Theme</th>
                <th style={{ width: 90 }}>When</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((f) => {
                const theme = f.theme_id ? themeMap.get(f.theme_id) : undefined;
                return (
                  <tr
                    key={f.id}
                    data-selected={selected?.id === f.id}
                    onClick={() => setSelected(f)}
                  >
                    <td>
                      <UrgencyDot urgency={f.urgency} />
                    </td>
                    <td>
                      <SourceTile source={f.source} />
                    </td>
                    <td className="num muted" style={{ fontSize: 11.5 }}>
                      {f.id}
                    </td>
                    <td style={{ maxWidth: 0, width: '100%' }}>
                      <span className="truncate" style={{ display: 'block', maxWidth: '100%' }}>
                        {f.text}
                      </span>
                    </td>
                    <td className="muted" style={{ fontSize: 12.5 }}>
                      {f.author || '—'}
                    </td>
                    <td>
                      {theme ? (
                        <span className="chip" data-tone="accent">
                          {theme.title.length > 22 ? `${theme.title.slice(0, 22)}…` : theme.title}
                        </span>
                      ) : (
                        <span className="muted">—</span>
                      )}
                    </td>
                    <td className="num muted">{timeAgo(f.created_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <FeedbackDrawer item={selected} themes={themeMap} onClose={() => setSelected(null)} />
    </div>
  );
}
