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

---

# Phase 2 contracts (closed-loop intelligence)

## 10. Provider-agnostic MCP surface (multi-transport)

`python -m mcp_server.server` grows CLI flags (argparse):
- `--transport stdio|sse|streamable-http` (default `stdio` — ADK toolset keeps working unchanged)
- `--host` (default `127.0.0.1`), `--port` (default `8765`), applied via `mcp.settings`
- streamable-http endpoint path: `/mcp` (FastMCP default `streamable_http_path`)

So ANY MCP-capable client (Claude Code/Desktop, Cursor, Gemini CLI, etc.) connects to the
same 16+ tools. New convenience read tool: `get_overview() -> {status, counts, urgent,
latest_brief_week}` (mirrors §5 /api/overview shape minus heavy lists).
`docs/CONNECT_ANY_AGENT.md` documents copy-paste configs: `claude mcp add` (stdio + http),
`.mcp.json`, Cursor `mcp.json`, Gemini CLI settings — plus a security note (bind localhost;
no auth layer in demo scope).

## 11. Skills (procedural knowledge the agents consult and extend)

- Layout: `skills/<kebab-name>/SKILL.md` (authored, committed) and
  `skills/learned/<kebab-name>/SKILL.md` (agent-written at runtime; gitignored except .gitkeep).
- SKILL.md format: YAML frontmatter `name`, `description` (one line, trigger-phrased),
  then markdown body = step-by-step procedure referencing MCP tools by exact name.
- Authored skills (exactly these five):
  1. `triage-feedback` — the full pipeline procedure + quality bar for themes/urgency.
  2. `write-weekly-brief` — brief structure (urgent → themes w/ trend → bets → contradictions).
  3. `escalate-churn-risk` — when/how to file a GitHub issue: evidence links, title format,
     directive check, ledger discipline.
  4. `fix-from-feedback` — bet → create_handoff → transfer to coder → verify tests →
     attach result → record action (the §12 loop).
  5. `answer-with-evidence` — how to answer operator questions: ids + counts + quotes, never
     invent; which read tools per question type.
- MCP tools (mcp_server, same naming/return conventions as §2):
  - `list_skills() -> {status, skills: [{name, description, source: "authored"|"learned"}]}`
  - `load_skill(name: str) -> {status, name, description, body}`
  - `save_skill(name: str, description: str, body: str) -> {status, name}` — writes ONLY
    under `skills/learned/` (path-traversal-safe: kebab-case validated, no separators);
    overwriting an authored skill is an error; overwriting a learned skill is allowed.
- Env `CLEO_SKILLS_DIR` overrides the skills root (tests use tmp dirs).
- Auto-use wiring (agents/cleo): the operator and actor instructions embed the skill INDEX
  (name+description, built at agent-construction time via a small loader in
  `agents/cleo/skills_index.py` reading the same dir) + the rule: "before any multi-step
  task, if a skill matches, call load_skill and follow it; after succeeding at a multi-step
  task no skill covered, call save_skill with a reusable procedure." Index injection is
  static-at-construction (cheap), load_skill is the dynamic path.

## 12. Handoffs + coder subagent (agent-orchestrating-agents)

- New collection `handoffs`:
  `{"id":"hf_…","bet_id":null|"bet_…","title":"…","problem":"…","evidence_ids":[],
    "acceptance":["…"],"status":"open|in_progress|done|failed",
    "result":{"files_changed":[],"tests":"","notes":""},"created_at":"…","finished_at":null}`
- MCP tools: `create_handoff(handoff: dict) -> {status,id}` (status defaults open),
  `get_handoff(id) -> {status, handoff}`, `list_handoffs(status: str = "") -> {status, handoffs}`,
  `update_handoff(id, status, result: dict|None) -> {status}` (sets finished_at on done/failed).
- **Coder subagent** (`agents/cleo/sub_agents/coder.py`): LlmAgent `coder`, model via
  `cleo_model()`, its OWN tools (plain ADK FunctionTools in `agents/cleo/coder_tools.py`,
  NOT MCP — sandboxing lives in-process):
  - `read_workspace_file(path)` / `list_workspace() ` / `write_workspace_file(path, content)`
    — all paths resolved under `workspace/` ONLY (reject `..`, absolute paths; resolve+check
    prefix). Write returns diff-style summary (lines added/removed).
  - `run_workspace_tests() -> {status, passed, failed, output_tail}` — runs
    `python -m pytest workspace/lumen_checkout/tests -q` via subprocess with 120s timeout,
    cwd=repo root, env stripped of GOOGLE_API_KEY.
  - plus store toolset filtered to `get_handoff`, `update_handoff`.
  - Instruction: take handoff id from session state key `handoff_id` (or ask), read code,
    make the SMALLEST fix satisfying acceptance, run tests until green, update_handoff done
    with files_changed + tests output, NEVER touch files outside workspace/.
- Operator wiring: `coder` added to `cleo_operator.sub_agents`; operator transfers to coder
  when a fix is requested (per `fix-from-feedback` skill), passing handoff id via state
  (`output_key`/instruction convention documented in code).
- `action_guard` unchanged (coder tools are FunctionTools, inherently workspace-scoped);
  every completed handoff also gets a `record_action` entry type `"code_fix"` (§1 actions
  type list grows: `github_issue|github_comment|brief|escalation|code_fix`).

## 13. Demo target app: `workspace/lumen_checkout/`

Tiny self-contained FastAPI app mirroring the corpus narrative (Lumen's billing service):
- `app.py`: `POST /billing/checkout {plan, seats, card_token}` — SEEDED BUG: when
  `plan == "business"` and `seats > 10` it raises (HTTP 500) due to a tier-pricing lookup
  using a key that doesn't exist (realistic one-line-ish bug, discoverable by reading code).
  v2.3 changelog comment in the file points at the regression, matching the corpus.
- `tests/test_checkout.py`: pytest suite that FAILS on the seeded bug (business+12 seats
  case) and passes once fixed — this is the coder's objective function. Marked so the MAIN
  repo suite skips it by default (`pytest.ini` testpaths stays `tests/`; workspace tests run
  only via `run_workspace_tests`).
- `workspace/README.md`: one paragraph framing ("the repo Cleo's coder operates on in the
  demo") + how to reset (`git checkout -- workspace/`).

## 14. Phase-2 API/UI deltas

- `GET /api/handoffs?status=` → `{handoffs}` (§12 shape) — app/api.py.
- `GET /api/skills` → `{skills}` (index only) — for the UI to render.
- Actions view gains a "Handoffs" section (id, title, status chip, files_changed count);
  Agent view header shows skill count ("N skills available") via /api/skills. Keep minimal.
