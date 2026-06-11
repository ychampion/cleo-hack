// Directives — declarative intent: list + add + toggle active.

import { useState } from 'react';
import { Icons } from '../lib/icons';
import { timeAgo } from '../lib/format';
import { useFetch } from '../lib/useFetch';
import {
  createDirective,
  listDirectives,
  setDirectiveActive,
  type Directive,
} from '../api';
import { EmptyState, ErrorState, Loading } from '../components/Primitives';

export function DirectivesView() {
  const directives = useFetch<Directive[]>(() => listDirectives(), []);
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyToggles, setBusyToggles] = useState<Set<string>>(new Set());

  const add = async () => {
    const t = text.trim();
    if (!t || saving) return;
    setSaving(true);
    setActionError(null);
    try {
      await createDirective(t);
      setText('');
      await directives.reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (d: Directive) => {
    if (busyToggles.has(d.id)) return;
    setBusyToggles((prev) => new Set(prev).add(d.id));
    setActionError(null);
    try {
      await setDirectiveActive(d.id, !d.active);
      await directives.reload();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyToggles((prev) => {
        const next = new Set(prev);
        next.delete(d.id);
        return next;
      });
    }
  };

  return (
    <div>
      <div className="page-h">
        <div>
          <h1>Directives</h1>
          <div className="lead">
            Declarative intent — standing instructions Cleo reads before every run.
            You state the outcome; the agent decides the steps.
          </div>
        </div>
      </div>
      <div className="page-body" style={{ maxWidth: 880 }}>
        <div className="dir-add">
          <input
            className="input"
            placeholder="e.g. Escalate urgent churn risks as GitHub issues in our demo repo…"
            value={text}
            disabled={saving}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void add();
            }}
          />
          <button
            className="btn"
            data-variant="primary"
            onClick={() => void add()}
            disabled={saving || !text.trim()}
          >
            {saving ? <span className="spin" /> : <Icons.Plus size={13} />} Add
          </button>
        </div>

        {actionError && (
          <ErrorState title="Directive update failed" error={actionError} />
        )}

        {directives.loading ? (
          <Loading label="Loading directives" />
        ) : directives.error ? (
          <ErrorState error={directives.error} onRetry={() => void directives.reload()} />
        ) : (directives.data ?? []).length === 0 ? (
          <EmptyState
            icon={<Icons.Shield size={20} />}
            title="No directives yet"
            body="Give Cleo standing intent — “keep the weekly brief current”, “escalate urgent churn risks as GitHub issues” — and it acts on them every run."
          />
        ) : (
          <div>
            {(directives.data ?? []).map((d) => (
              <div key={d.id} className="dir-row" data-active={d.active}>
                <button
                  className="switch"
                  data-on={d.active}
                  onClick={() => void toggle(d)}
                  disabled={busyToggles.has(d.id)}
                  title={d.active ? 'Active — click to pause' : 'Paused — click to activate'}
                  aria-pressed={d.active}
                />
                <div className="txt">{d.text}</div>
                <div className="when">{timeAgo(d.created_at)}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
