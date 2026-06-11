# CONTRACTS — single integration spec (all components build against this)

Anything not specified here is the component owner's choice. Changing a contract requires
updating this file in the same commit.

## 0. Conventions

- Python 3.12, `uv` for deps, `bun` for web. Ports: API **8080**, Vite dev **5173**.
- Model id: **`gemini-3.5-flash`** (exact string; env-overridable via `CLEO_MODEL`).
- SQLite file: `data/cleo.db` (env `CLEO_DB_PATH`). Single `documents` table:
  `(collection TEXT, id TEXT, payload TEXT/*json*/, created_at TEXT, PRIMARY KEY(collection,id))`
  — store module: `mcp_server/store.py`, class `Store` with `put(collection, id, doc)`,
  `get`, `list(collection, **filters)`, `delete`. WAL mode. No ORM.
- All ids: `<prefix>_<12 hex>` (fb_, th_, bet_, act_, br_, dir_, run_).
- All timestamps ISO-8601 UTC strings.

## 1. Data shapes (payload JSON)

```jsonc
// collection "feedback"
{"id":"fb_…","source":"github|intercom|slack|call|doc","external_id":"…","author":"…",
 "text":"…","url":null,"created_at":"…","ingested_at":"…",
 "urgency":null /*0-3 set by agent*/,"sentiment":null /*"pos|neu|neg"*/,
 "theme_id":null,"metadata":{}}

// collection "themes"
{"id":"th_…","title":"…","summary":"…","urgency":0,"trend":"new|rising|steady",
 "feedback_ids":["fb_…"],"first_seen":"…","last_seen":"…"}

// collection "bets"
{"id":"bet_…","title":"…","problem":"…","proposal":"…","impact":1-5,"effort":1-5,
 "confidence":0.0-1.0,"urgency":0-3,"theme_ids":[],"evidence_ids":["fb_…"],
 "status":"proposed|approved|shipped","created_at":"…"}

// collection "actions"  (the autonomous-action ledger)
{"id":"act_…","type":"github_issue|github_comment|brief|escalation",
 "status":"proposed|executed|failed|skipped","target":"repo#… or brief id",
 "payload":{},"rationale":"…","evidence_ids":[],"created_at":"…","executed_at":null,
 "result":{}}

// collection "briefs"
{"id":"br_…","week":"2026-W24","markdown":"…","theme_ids":[],"created_at":"…"}

// collection "directives"  (declarative intent)
{"id":"dir_…","text":"…","active":true,"created_at":"…"}

// collection "runs"  (agent run ledger for the UI)
{"id":"run_…","trigger":"manual|loop","started_at":"…","finished_at":null,
 "status":"running|done|error","summary":"…",
 "counts":{"ingested":0,"themes":0,"bets":0,"actions":0}}
```

## 2. MCP server `cleo-feedback-store` (`mcp_server/server.py`, FastMCP, stdio)

Launch: `uv run python -m mcp_server.server` (module must support `python -m`).
Tools (names exact; args/returns JSON-serializable dicts; every return includes `"status":"success"|"error"`):

- `ingest_feedback(items: list[dict]) -> {status, ingested, duplicates}` (dedupe on source+external_id)
- `list_feedback(source: str = "", only_untriaged: bool = False, limit: int = 50) -> {status, items}`
- `search_feedback(query: str, limit: int = 20) -> {status, items}` (LIKE/keyword ok)
- `tag_feedback(updates: list[dict]) -> {status, updated}`  // {id, urgency?, sentiment?, theme_id?}
- `save_themes(themes: list[dict]) -> {status, saved}`  // upsert; assigns ids if missing
- `list_themes() -> {status, themes}`
- `save_bets(bets: list[dict]) -> {status, saved}`
- `list_bets() -> {status, bets}`
- `record_action(action: dict) -> {status, id}`        // status defaults "proposed"
- `complete_action(id: str, status: str, result: dict) -> {status}`
- `list_actions(status: str = "") -> {status, actions}`
- `write_brief(markdown: str, theme_ids: list[str]) -> {status, id}`
- `get_latest_brief() -> {status, brief}`             // brief may be null
- `get_directives() -> {status, directives}`          // active only
- `start_run(trigger: str) -> {status, id}` / `finish_run(id, summary, counts) -> {status}`

## 3. External MCP connectors (configured in `agents/cleo/agent.py`)

- **GitHub (real):** primary = hosted GitHub MCP `https://api.githubcopilot.com/mcp/` via
  `StreamableHTTPConnectionParams(headers={"Authorization": "Bearer $GITHUB_TOKEN"})`,
  `tool_filter=["list_issues","search_issues","create_issue","add_issue_comment"]`.
  Fallback (if hosted unreachable at build time): stdio `npx -y @modelcontextprotocol/server-github`.
  Wrap construction in `make_github_toolset()`; skip gracefully when `GITHUB_TOKEN` unset.
- **Filesystem (real):** stdio `npx -y @modelcontextprotocol/server-filesystem <abs path to seed/corpus>`
  `tool_filter=["list_directory","read_file"]` — used by ingest for call-transcripts/docs.

## 4. ADK app (`agents/cleo/`)

- Dir layout works with both `adk web agents` and programmatic Runner. `agents/cleo/agent.py`
  defines `root_agent`. Model from `CLEO_MODEL` env, default `gemini-3.5-flash`.
- `root_agent = cleo_operator` (LlmAgent): answers questions about current state (via store
  toolset) AND delegates to `triage_pipeline` sub-agent when asked to triage/run.
- `triage_pipeline` (SequentialAgent): `ingest_stage` (ParallelAgent of per-source LlmAgents:
  github_ingestor, docs_ingestor, corpus sources read via store `ingest_feedback`) →
  `synthesizer` (clusters + tags urgency/sentiment/contradictions; saves themes;
  output_key="synthesis") → `prioritizer` (LlmAgent, `output_schema=BetProposals`,
  output_key="bets"; afterwards saved via callback or tool) → `actor` (LlmAgent: reads
  directives, records actions, executes GitHub writes via MCP, writes brief).
- `watch_loop` (LoopAgent around triage_pipeline, max_iterations=3) exposed as sub-agent
  for "continuous" demo.
- `callbacks.py`: `action_guard` (before_tool_callback): GitHub write tools allowed only if an
  active directive contains "escalate" or explicit approval flag in session state; every write
  also `record_action`-ed. `run_recorder` (after_agent_callback on pipeline): finish_run with counts.
- `schemas.py`: Pydantic `BetProposal`/`BetProposals` matching §1 bets shape.

## 5. FastAPI app (`app/main.py`)

`get_fast_api_app(agents_dir="agents", web=False)` + custom routes (all return the §1 shapes):

- `GET /api/overview` → `{counts:{feedback,untriaged,themes,bets,actions_executed}, urgent: theme[], latest_brief, recent_actions: action[5], top_themes: theme[5]}`
- `GET /api/feedback?source=&theme_id=&urgency=&limit=` → `{items}`
- `GET /api/themes` / `GET /api/bets` / `GET /api/actions?status=` / `GET /api/briefs/latest`
- `GET /api/directives` / `POST /api/directives {text}` / `PATCH /api/directives/{id} {active}`
- `POST /api/agent/run {message?: str}` → creates ADK session if needed (app_name="cleo",
  user "operator", session "ui"), returns `{run_id}`; events stream at ADK's own
  `POST /run_sse` (UI calls it directly with the same session triple).
- `GET /api/runs` / `GET /api/runs/{id}`
- `GET /api/runtime/status` → `{model, google_api_key_present, github_token_present, db_path, feedback_count}`
- CORS: allow `http://localhost:5173`. Serve `web/dist` at `/` when built (mount AFTER api routes).

Run: `uv run uvicorn app.main:app --port 8080`.

## 6. Web (`web/`) — Vite + React 18 + TS

- Design: copy tokens/components style from `design-ref/.cleo-design-3/cleo/project/`
  (primitives.jsx, app-shell.jsx, icons.jsx, styles.css) — Geist font, ink `#0A0A0A`, accent
  `#1F6FEB`, hairline borders, mono numerals, NO card-on-card, hand-rolled icons (adapt to TSX).
- Views: Brief (default), Inbox, Themes, Bets, Actions, Agent (run button + live SSE trace),
  Directives. Sidebar shell + topbar like design.
- Dev proxy: `/api` and `/run_sse` etc → `http://127.0.0.1:8080`. Build output `web/dist`.
- API client in `web/src/api.ts` typed to §1 shapes + §5 routes ONLY (no invented endpoints).

## 7. Seed (`seed/`)

- `seed/corpus/` raw realistic sources: `slack-export.json` (~30 msgs), `tickets.json` (~25),
  `call-transcripts/*.md` (3 files), `docs/*.md` (2 NPS/notes docs). Engineered narrative:
  SaaS startup "Lumen" (team-analytics tool); themes ≈ checkout-500s after v2.3 (URGENT,
  churn threats), Okta SSO broken (URGENT), CSV export requests, dashboard slowness,
  onboarding confusion, API webhooks ask; 1 contradiction (default email digests on vs off).
- `seed/seed.py`: loads corpus → `ingest_feedback` direct via store (no LLM), seeds 2
  directives ("Triage all new feedback…escalate urgent churn risks as GitHub issues in
  $GITHUB_DEMO_REPO", "Keep the weekly product brief current"). Idempotent.
  Run: `uv run python -m seed.seed`.

## 8. Env (`.env.example`)

GOOGLE_GENAI_USE_VERTEXAI=FALSE, GOOGLE_API_KEY=, CLEO_MODEL=gemini-3.5-flash,
CLEO_DB_PATH=data/cleo.db, GITHUB_TOKEN=, GITHUB_DEMO_REPO=owner/repo,
CORPUS_DIR=seed/corpus.

## 9. Tests (`tests/`, pytest, NO network/LLM)

- `test_store.py` (CRUD, filters), `test_mcp_server.py` (call tool fns directly as Python),
  `test_api.py` (FastAPI TestClient against §5; monkeypatch agents dir if needed),
  `test_seed.py` (seed idempotency, corpus integrity).
- Live verification (needs keys, NOT in pytest): `scripts/live_smoke.py` — checks model ping,
  MCP server boots, optional GitHub MCP list, then one full `triage` run.
