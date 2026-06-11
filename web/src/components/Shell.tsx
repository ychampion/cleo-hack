// Cleo — app shell: sidebar + topbar, per the canonical design (app-shell.jsx).

import { NavLink, Outlet, useLocation, useNavigate } from 'react-router';
import { Icons, type IconProps } from '../lib/icons';
import { useOverview } from '../lib/overview';
import { useFetch } from '../lib/useFetch';
import { getRuntimeStatus, type RuntimeStatus } from '../api';

interface NavEntry {
  to: string;
  label: string;
  icon: (p: IconProps) => JSX.Element;
  section: string;
  end?: boolean;
}

const NAV: NavEntry[] = [
  { to: '/', label: 'Brief', icon: Icons.Spec, section: 'Workspace', end: true },
  { to: '/inbox', label: 'Inbox', icon: Icons.Inbox, section: 'Workspace' },
  { to: '/themes', label: 'Themes', icon: Icons.Layers, section: 'Workspace' },
  { to: '/bets', label: 'Bets', icon: Icons.Chart, section: 'Workspace' },
  { to: '/actions', label: 'Actions', icon: Icons.Ledger, section: 'Autonomy' },
  { to: '/agent', label: 'Agent', icon: Icons.Sparkle, section: 'Autonomy' },
  { to: '/directives', label: 'Directives', icon: Icons.Shield, section: 'Autonomy' },
];

const SECTIONS = ['Workspace', 'Autonomy'];

function Sidebar() {
  const navigate = useNavigate();
  const { data: overview } = useOverview();
  const untriaged = overview?.counts?.untriaged ?? 0;
  return (
    <aside className="sidebar">
      <div className="sidebar-head">
        <div className="sidebar-logo">C</div>
        <div className="sidebar-name">Cleo</div>
      </div>
      <div className="sidebar-org">
        <div className="org-dot" />
        <div className="truncate">Lumen · Pilot</div>
      </div>
      <button
        className="sidebar-run"
        onClick={() => navigate('/agent')}
        title="Open the agent and run triage"
      >
        <Icons.Sparkle size={14} />
        <span className="label">Run triage</span>
      </button>
      {SECTIONS.map((sec) => (
        <div key={sec}>
          <div className="sidebar-section">{sec}</div>
          <nav className="nav">
            {NAV.filter((n) => n.section === sec).map((n) => {
              const Ico = n.icon;
              return (
                <NavLink key={n.to} to={n.to} end={n.end} className="nav-item">
                  <Ico size={14} />
                  <span>{n.label}</span>
                  {n.to === '/inbox' && untriaged > 0 && (
                    <span className="badge">{untriaged}</span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>
      ))}
      <div className="sidebar-foot">
        <div className="avatar">OP</div>
        <div className="who">
          <div className="name">Operator</div>
          <div className="role">Lumen · Product</div>
        </div>
      </div>
    </aside>
  );
}

function RuntimeChip() {
  const { data } = useFetch<RuntimeStatus>(() => getRuntimeStatus(), []);
  if (!data) return null;
  return (
    <span
      className="runtime-chip"
      title={`db ${data.db_path} · ${data.feedback_count} feedback items`}
    >
      <span>{data.model}</span>
      <span className="d" data-on={data.google_api_key_present} title="GOOGLE_API_KEY" />
      <span className="d" data-on={data.github_token_present} title="GITHUB_TOKEN" />
    </span>
  );
}

function TopBar() {
  const { pathname } = useLocation();
  const entry =
    NAV.find((n) => (n.end ? pathname === n.to : pathname.startsWith(n.to) && n.to !== '/')) ??
    NAV[0];
  return (
    <div className="topbar">
      <div className="crumb">
        <span>Lumen</span>
        <span className="sep">/</span>
        <b>{entry.label}</b>
      </div>
      <div className="topbar-spacer" />
      <RuntimeChip />
    </div>
  );
}

export function Shell() {
  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <TopBar />
        <div className="main-body">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
