# Demo script (3 minutes)

**Setup before recording:** `uv run python -m seed.seed` done, API running on 8080, web built
or `bun run dev`, `.env` has GOOGLE_API_KEY + GITHUB_TOKEN + GITHUB_DEMO_REPO, demo repo open
in a browser tab.

## 0:00 — The problem (20s)
"This is Lumen, a 9-person startup. Their user feedback lives in Slack threads, support
tickets, sales-call transcripts and docs. Nobody reads all of it. Urgent issues hide in the
noise for days." *Show Inbox: 90+ raw items from 5 sources, untriaged.*

## 0:20 — Declarative intent (20s)
*Open Directives.* "We don't script the agent. We state intent: **triage all new feedback,
escalate urgent churn risks as GitHub issues, keep the weekly brief current.** Cleo figures
out the rest." 

## 0:40 — The agent runs (70s)
*Open Agent, click Run triage.* Narrate the live trace as it streams:
- "Ingestors run **in parallel** — GitHub issues over the GitHub MCP server, call transcripts
  over the filesystem MCP server. Every tool call you see crosses an MCP boundary."
- "The synthesizer clusters ~90 items into 7 themes — it found the checkout-500 spike
  (31 signals) and the broken Okta SSO (21 signals) and flagged both urgent, and it caught a
  real contradiction: enterprise wants email digests off by default, SMBs want them on."
- "The prioritizer emits structured product bets — typed JSON, not prose."
- "Now the actor: it checks the directives, and **acts**."

## 1:50 — Autonomy with accountability (40s)
*Switch to the GitHub repo tab:* a new issue "Checkout 500s after v2.3 — 31 signals, severe
churn threats" with evidence links. *Back to Actions view:* the ledger shows every action — executed
ones with results, plus one **blocked** write the guard stopped (no directive covered it).
"Every autonomous action carries its rationale and evidence. Nothing happens off the books."

## 2:30 — The payoff (30s)
*Open Brief.* "The weekly product brief wrote itself: urgent issues, rising themes, three
evidence-backed bets ranked by impact and effort. What took a PM an afternoon now takes one
agent run — and it never misses a churn threat in a Tuesday-night Slack thread."

"Built on ADK — Sequential, Parallel and Loop agents, structured outputs, callback guardrails —
with every connector speaking MCP, on gemini-3.5-flash."
