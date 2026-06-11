# Demo script (~3:15)

**Setup before recording:** `uv run python -m seed.seed` done, API on 8080, web built (or
`bun run dev`), `.env` has GOOGLE_API_KEY (paid tier) + GITHUB_TOKEN + GITHUB_DEMO_REPO,
demo GitHub repo open in a second tab, `git checkout -- workspace/` run so the seeded bug is
present. Rehearse once end-to-end.

## 0:00 — The problem (20s)
"This is Lumen, a 9-person startup. User feedback lives in Slack threads, support tickets,
sales-call transcripts and docs. Nobody reads all of it; urgent issues hide for days."
*Show Inbox: ~90 raw items from 5 sources, untriaged.*

## 0:20 — Declarative intent (15s)
*Open Directives.* "We don't script the agent — we state intent: **triage all feedback,
escalate urgent churn risks as GitHub issues, keep the weekly brief current.** Cleo decides
the steps."

## 0:35 — The agent runs, live (60s)
*Open Agent, click Run triage.* Narrate the trace:
- "First it consults its **skills** — versioned runbooks it follows, and extends when it
  learns something new."
- "Ingestors run **in parallel** — GitHub issues through the GitHub MCP server, call
  transcripts through the filesystem MCP server. Every tool call crosses an MCP boundary."
- "The synthesizer clusters ~90 items into 7 themes — the checkout-500 spike (31 signals)
  and broken Okta SSO (21) flagged urgent; it even caught a real contradiction between
  enterprise and SMB customers."
- "The prioritizer emits structured product bets — typed JSON, evidence-linked."

## 1:35 — Autonomy with accountability (30s)
*GitHub tab:* a new issue "Checkout 500s after v2.3 — 31 signals, severe churn threats" with
evidence links. *Actions view:* the ledger — every action with rationale and evidence; one
blocked write the guardrail stopped. "Nothing happens off the books."

## 2:05 — The fix loop (45s) — the moment
*Agent view, type:* "Fix the checkout bug." Narrate:
- "The operator loads its `fix-from-feedback` skill, opens a **handoff** with testable
  acceptance criteria, and transfers to the **coder** — a second agent with its own context
  and its own sandboxed tools."
- *Trace shows:* coder reads `workspace/lumen_checkout/app.py`, edits the tier-pricing
  lookup, runs the test suite — red to green.
- *Actions view:* a `code_fix` entry with files changed and test output. "From customer
  complaint to a test-proven code fix — one conversation, full audit trail."

## 2:50 — The payoff (25s)
*Open Brief.* "The weekly brief wrote itself: urgent issues, rising themes, evidence-backed
bets. What took a PM an afternoon is one agent run — and it never misses a churn threat in a
Tuesday-night Slack thread."

"Built on ADK — Sequential, Parallel and Loop agents, structured outputs, callback
guardrails, sub-agent delegation — every connector speaking MCP, on gemini-3.5-flash. And
because the store is a standard MCP server, your own tools — Claude Code, Cursor, Gemini
CLI — can operate Cleo directly."

## Reset between takes

```bash
git checkout -- workspace/        # restore the seeded bug
uv run cleo status --json         # sanity: store + skills + key all present
```
