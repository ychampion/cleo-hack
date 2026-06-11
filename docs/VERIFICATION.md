# Verification gates

Run these in order. Gates 1–4 need **no keys** (offline, deterministic); gates 5–7 need the
real `.env` (GOOGLE_API_KEY; GITHUB_TOKEN optional but recommended).

## Gate 1 — offline test suite

```bash
uv run pytest -q
```
Expect: all green. Covers store CRUD/dedupe, every MCP tool function, REST routes, seed
idempotency. No network, no LLM.

## Gate 2 — MCP server boots over real stdio

```bash
uv run python -m mcp_server.server   # should start and wait on stdio; Ctrl+C to exit
```

## Gate 3 — seed + API + UI (deterministic data path)

```bash
uv run python -m seed.seed                      # expect: counts printed, idempotent on re-run
uv run uvicorn app.main:app --port 8080 &
curl -s localhost:8080/api/runtime/status       # model, key presence, feedback_count > 0
curl -s localhost:8080/api/overview             # counts populated, urgent themes []
cd web && bun run dev                           # all 7 views render with seeded data / designed empty states
```

## Gate 4 — SPA production build

```bash
cd web && bun run build && cd ..
# restart uvicorn; http://localhost:8080/ now serves the built UI
```

## Gate 5 — live model ping + full smoke (needs GOOGLE_API_KEY)

```bash
uv run python scripts/live_smoke.py
```
Expect, in order: model ping OK (gemini-3.5-flash) → MCP store tools listed over stdio →
GitHub MCP list_issues OK (if token set) → one full triage run with event trace → exit 0.

## Gate 6 — the demo loop (needs GITHUB_TOKEN + GITHUB_DEMO_REPO)

1. UI → Directives: confirm the escalation directive is active.
2. UI → Agent → Run triage. Watch the live trace: parallel ingest → synthesis → bets → actions.
3. Verify in GitHub: new issue exists with evidence links.
4. UI → Actions: ledger shows executed actions with rationale; any unauthorized write shows
   as blocked/skipped.
5. UI → Brief: weekly brief regenerated.

## Gate 7 — judging-criteria self-check

- [ ] Technical (30%): ADK concept map in README all true in code (Sequential/Parallel/Loop,
      output_schema, callbacks, McpToolset stdio+HTTP, Runner)? Code documented?
- [ ] Business (30%): README problem/payoff sharp? Demo shows hours→minutes?
- [ ] Innovation (20%): directives (declarative intent) + accountable autonomy ledger visible
      in the demo?
- [ ] Demo & docs (20%): 3-min script rehearsed? Architecture diagram current? Quickstart
      reproducible from clean clone?
