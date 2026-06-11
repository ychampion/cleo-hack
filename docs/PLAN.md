# Cleo — Build Plan (Google Agent Hackathon, Track 1: Build Net-New Agents)

## Problem

Startups get constant feedback from users across chats, tickets, calls and docs — but it sits
scattered and unused. Founders and PMs waste hours manually reading, tagging and guessing what
to build next, and still miss the real patterns and urgent issues.

## Solution — declarative intent, not static code

**Cleo** is an autonomous product-feedback operator. You give it a standing **directive**
("keep my product priorities true to the evidence; escalate churn risks immediately") and it
autonomously: connects to where feedback lives (via **MCP**), gathers and clusters it into
themes, detects urgent issues and contradictions, proposes evidence-backed product bets, and
**acts** — filing GitHub issues with evidence links, writing the weekly product brief, and
keeping an auditable action ledger. The team reviews outcomes, not raw feedback.

This is the Track-1 archetype (the HVAC agent that lowers heating from calendar data) applied
to product development: instead of reporting data, Cleo executes the intent.

## Architecture (see docs/ARCHITECTURE.md for the diagram)

1. **ADK orchestration engine** (`agents/cleo/`, `google-adk`, model `gemini-3.5-flash`):
   - `cleo_operator` (root `LlmAgent`) — conversational operator + dispatcher.
   - `triage_pipeline` (`SequentialAgent`): ingest → synthesize → prioritize → act.
   - `ingest_stage` (`ParallelAgent`): one agent per source pulls via MCP concurrently.
   - `watch_loop` (`LoopAgent`): continuous autonomous mode with escalation stop.
   - `output_schema` (Pydantic) for structured bets; `output_key` state passing between stages;
     `before_tool_callback` guardrails (action policy + ledger); `after_agent_callback` run summaries.
2. **MCP everywhere** (the only way the agent touches the world):
   - `mcp_server/` — **cleo-feedback-store**, a real FastMCP stdio server owning the SQLite
     store (feedback, themes, bets, actions, briefs, directives, runs).
   - **GitHub MCP server** (official, real) — read issues as a feedback source; create
     issues/comments as autonomous actions. Hosted endpoint via `StreamableHTTPConnectionParams`
     with PAT, fallback local server via stdio.
   - Filesystem MCP server (official) — ingest docs/call-transcripts from `seed/corpus/`.
3. **FastAPI app** (`app/`): `get_fast_api_app()` wraps the ADK runner (gives `/run`,
   `/run_sse`, sessions) + custom `/api/*` routes for the UI + serves built SPA.
4. **Web UI** (`web/`): single canonical UI from the original Claude design (Geist,
   ink #0A0A0A, accent #1F6FEB, hairlines, hand-rolled icons). Views: Brief, Inbox, Themes,
   Bets, Actions (ledger), Agent (live run trace via SSE), Directives.
5. **Seed corpus** (`seed/`): realistic multi-source feedback (chat export, tickets, call
   transcripts, docs) engineered to produce clear themes, 2 urgent issues, 1 contradiction.

## Judging-criteria mapping

| Criterion | How we score it |
|---|---|
| **Technical Implementation (30%)** | Core ADK concepts used for real: LlmAgent + SequentialAgent + ParallelAgent + LoopAgent, output_schema/output_key state, callbacks as guardrails, McpToolset over both stdio and Streamable HTTP, Runner + sessions, `adk eval` set, tests. Small, clean, documented codebase. |
| **Business Case (30%)** | Universal startup pain (every team drowns in scattered feedback); hours→minutes triage; urgent churn-risks surfaced same-day; works on a startup's existing GitHub from minute one (real connector, not mock). |
| **Innovation (20%)** | "Product CI": continuous integration for product decisions. Declarative intent via standing directives; autonomy with accountability (every autonomous action carries rationale + evidence links in an auditable ledger). |
| **Demo & Presentation (20%)** | 3-min script: seed → directive → watch the agent run live (UI trace + adk web events) → GitHub issue appears with evidence → weekly brief written. Architecture diagram + README explains exactly which ADK pieces do what. |

## Build order

1. Scaffold + CONTRACTS.md (single integration spec) — done first, everything builds against it.
2. Parallel: `mcp_server/`+`seed/` ‖ `agents/`+`app/` ‖ `web/`.
3. Integration pass: wire SPA → FastAPI → ADK → MCP; run pipeline deterministically (tests),
   then live smoke once `GOOGLE_API_KEY` is added.
4. Docs: README, architecture diagram, demo script, GCP setup. Verify all 4 criteria.

## Non-goals (timebox)

Auth/multi-tenant, deployment hardening beyond a working Cloud Run path, more than 2 real
write-connectors, mobile layouts.
