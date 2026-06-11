# AGENTS.md — for coding agents working in this repo

Cleo is an autonomous product-feedback operator: Google ADK agents (`gemini-3.5-flash`) that
ingest multi-source customer feedback through MCP connectors, cluster it into themes, propose
evidence-backed bets, and act — GitHub escalations, a weekly brief — under standing
directives, with every action in an auditable ledger.

## The one binding rule

**`CONTRACTS.md` is the integration spec and it is binding.** Data shapes, MCP tool names and
return shapes, REST routes, env vars, ports — all live there. Change a contract and its
implementation in the same commit. Anything not in CONTRACTS.md is the component owner's call.

## Layout

| Path | What it is |
|---|---|
| `agents/cleo/` | ADK app: `agent.py` (root operator + triage pipeline + watch loop), `sub_agents/` (ingestors, synthesizer, prioritizer, actor, coder), `toolsets.py` (MCP toolset factories), `callbacks.py` (`action_guard`, run ledger), `model.py`, `schemas.py`, `skills_index.py` |
| `mcp_server/` | `cleo-feedback-store`: FastMCP server (stdio / sse / streamable-http) over SQLite (`store.py`, `data/cleo.db`) |
| `app/` | FastAPI: `main.py` (`get_fast_api_app` + SPA mount), `api.py` (`/api/*`), `config.py` (workspace config: env > `cleo.config.json` > defaults) |
| `web/` | React + Vite + TS SPA (bun) |
| `seed/` | Demo corpus + idempotent seeder |
| `skills/` | Procedural skills (`SKILL.md`); `skills/learned/` is agent-written at runtime |
| `workspace/` | Sandboxed demo repo the coder subagent operates on (never touch from elsewhere) |
| `tests/` | Offline suite — the green gate |
| `docs/` | GET_STARTED, ARCHITECTURE, CONNECT_ANY_AGENT, DEMO, VERIFICATION, GCP_SETUP, PLAN |

## Commands

```bash
uv sync                                   # Python deps (3.12+, uv — never pip directly)
uv run pytest -q                          # offline gate — must stay green
uv run python -m seed.seed                # seed demo corpus (idempotent)
uv run uvicorn app.main:app --port 8080   # API + agent + built SPA
uv run python -m mcp_server.server        # standalone MCP server (stdio default)
cd web && bun install && bun run dev      # UI dev on :5173 (bun, never npm)
cd web && bun run build                   # SPA -> web/dist
cleo triage                               # headless CLI run (see docs/CLI.md)
uv run python scripts/live_smoke.py       # live verification (needs GOOGLE_API_KEY)
```

## Conventions

- `uv` for Python, `bun` for web. Ports: API **8080**, Vite **5173**. Model id
  `gemini-3.5-flash` exactly (env `CLEO_MODEL`).
- **Tests are offline-only**: no network, no LLM calls. Live checks belong in
  `scripts/live_smoke.py`, never in `tests/`.
- Every MCP tool returns a JSON-serializable dict with `"status": "success"|"error"`.
  Ids are `<prefix>_<12 hex>` (`fb_`, `th_`, `bet_`, `act_`, `br_`, `dir_`, `run_`, `hf_`);
  timestamps are ISO-8601 UTC strings.
- The agent touches the world **only through MCP toolsets** with least-privilege
  `tool_filter`s; external writes pass the `action_guard` callback and land in the actions
  ledger. Never add direct side-effect tools.
- **Design-system law** (`web/`): Geist, ink `#0A0A0A`, accent `#1F6FEB`, hairline borders,
  mono numerals, hand-rolled icons, no card-on-card, no external UI libraries.
- Workspace settings (repo, corpus dirs, model, workspace name) resolve through
  `app/config.py` — read them via `get_config()`, don't re-read raw env in new code.

## Pointers

`docs/GET_STARTED.md` (run on your own company) · `docs/ARCHITECTURE.md` (agent tree +
diagram) · `docs/CONNECT_ANY_AGENT.md` (connect any MCP client) · `docs/VERIFICATION.md`
(gate-by-gate checks) · `llms.txt` (machine-readable doc index)
