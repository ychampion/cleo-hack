# cleo-hack — Project Instructions

Autonomous product-feedback operator. Google ADK orchestration + MCP connectors +
`gemini-3.5-flash` (exact id, env `CLEO_MODEL`). Hackathon Track 1: net-new agent,
declarative intent, autonomous execution.

## Rules

- **CONTRACTS.md is binding.** Every interface (data shapes, MCP tools, REST routes, env)
  lives there; change the contract and the implementation in the same commit.
- **One UI.** The design system (Geist, ink #0A0A0A, accent #1F6FEB, hairlines, hand-rolled
  icons, no card-on-card) is law. Never introduce a second design direction or a UI library.
- `uv` for Python (`uv run pytest`), `bun` for web. Ports: API 8080, Vite 5173.
- Tests must stay network-free and LLM-free; live checks belong in `scripts/live_smoke.py`.
- The agent touches the world only through MCP toolsets; external writes go through the
  `action_guard` callback and the actions ledger. Don't add direct side-effect tools.

## Map

`agents/cleo/` ADK app (root operator, triage pipeline, watch loop) · `mcp_server/` FastMCP
feedback store + SQLite · `app/` FastAPI (`get_fast_api_app` + `/api/*` + SPA) · `web/` SPA ·
`seed/` demo corpus + seeder · `docs/` PLAN, ARCHITECTURE (diagram), DEMO, GCP_SETUP.

## Run

```bash
uv run python -m seed.seed
uv run uvicorn app.main:app --port 8080
cd web && bun run dev          # http://localhost:5173
uv run pytest -q               # offline gate
uv run python scripts/live_smoke.py   # needs GOOGLE_API_KEY (+ GITHUB_TOKEN optional)
```
