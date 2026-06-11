# Architecture

Cleo is a net-new autonomous agent: an **ADK orchestration engine** that touches the world
exclusively through **MCP**, driven by **declarative intent** (standing directives) rather
than imperative scripts, with every autonomous action recorded in an auditable ledger.

## Diagram

```mermaid
flowchart TB
    subgraph UI["Web UI — React + Vite (single Claude-design system)"]
        BR[Brief] ; IN[Inbox] ; TH[Themes] ; BE[Bets] ; AC["Actions (ledger)"] ; AG["Agent (live trace)"] ; DI["Directives (declarative intent)"]
    end

    subgraph API["FastAPI service (app/) — get_fast_api_app + custom routes"]
        REST["/api/* dashboard routes"]
        SSE["/run_sse — ADK event stream"]
    end

    subgraph ADK["ADK Orchestration Engine (agents/cleo) — model: gemini-3.5-flash"]
        OP["cleo_operator (root LlmAgent)<br/>conversational operator + dispatcher"]
        subgraph PIPE["triage_pipeline (SequentialAgent)"]
            direction LR
            ING["ingest_stage<br/>(ParallelAgent:<br/>per-source ingestors)"] --> SYN["synthesizer<br/>(cluster themes,<br/>urgency, contradictions)"] --> PRI["prioritizer<br/>(output_schema:<br/>BetProposals)"] --> ACT["actor<br/>(directives → actions)"]
        end
        LOOP["watch_loop (LoopAgent)<br/>continuous autonomous mode"]
        GUARD["callbacks: action_guard (before_tool)<br/>+ run_recorder (after_agent)"]
        OP --> PIPE
        OP --> LOOP
        LOOP --> PIPE
        GUARD -.-> ACT
    end

    subgraph MCP["Model Context Protocol boundary (all world access)"]
        STORE["cleo-feedback-store<br/>FastMCP server (stdio)<br/>feedback/themes/bets/actions/<br/>briefs/directives/runs"]
        GH["GitHub MCP server (real)<br/>Streamable HTTP + PAT<br/>list/search/create issues"]
        FS["Filesystem MCP server (real)<br/>docs & call transcripts"]
    end

    DB[("SQLite<br/>data/cleo.db")]
    GHE[("GitHub<br/>(live repo)")]
    CORPUS[("seed/corpus<br/>chats · tickets · calls · docs")]

    UI -->|REST| REST
    AG -->|stream| SSE
    REST -->|reads| DB
    SSE --> OP
    PIPE -->|McpToolset stdio| STORE
    PIPE -->|McpToolset HTTP| GH
    ING -->|McpToolset stdio| FS
    STORE --> DB
    GH --> GHE
    FS --> CORPUS
```

## The loop (what actually happens on a run)

1. A **directive** exists — e.g. *"Triage all new feedback; escalate urgent churn risks as
   GitHub issues; keep the weekly brief current."* This is the declarative intent: outcome,
   not procedure.
2. `cleo_operator` (or the `watch_loop` in continuous mode) launches `triage_pipeline`.
3. **Ingest** — `ParallelAgent` fans out one ingestor per source concurrently: GitHub issues
   via the GitHub MCP server, docs/call transcripts via the filesystem MCP server, chat/ticket
   exports already staged in the store. Everything lands as normalized `feedback` rows
   (deduped) via `cleo-feedback-store` MCP tools.
4. **Synthesize** — clusters feedback into `themes`, tags urgency/sentiment, flags
   contradictions; writes themes back through MCP. Summary flows to the next stage via ADK
   session state (`output_key="synthesis"`).
5. **Prioritize** — emits structured `BetProposals` (Pydantic `output_schema`; tool-free by
   ADK design, reading `{synthesis}` from state) — evidence-linked product bets with
   impact/effort/confidence.
6. **Act** — reads the directives, then executes: records every intended action in the
   `actions` ledger, files real GitHub issues (with evidence links back to feedback), writes
   the weekly brief. The `action_guard` callback gates every write tool call — no directive
   authorizing escalation ⇒ the call is blocked and recorded as `skipped`. Autonomy **with
   accountability**.
7. The UI's Agent view streams the whole run live from ADK's `/run_sse`; the Actions view
   shows the ledger; the Brief view shows the outcome.

## ADK concept map (what we used and why)

| ADK concept | Where | Why |
|---|---|---|
| `LlmAgent` (`gemini-3.5-flash`) | operator, ingestors, synthesizer, prioritizer, actor | reasoning units |
| `SequentialAgent` | `triage_pipeline` | the four stages have strict data dependencies |
| `ParallelAgent` | `ingest_stage` | sources are independent; concurrency is free wall-clock |
| `LoopAgent` | `watch_loop` | continuous autonomous mode with bounded iterations |
| `output_schema` (Pydantic) | prioritizer | bets must be machine-usable, not prose |
| `output_key` / session state | between all stages | typed hand-off without re-prompting |
| `before_tool_callback` | `action_guard` | hard guardrail: directives gate external writes |
| `after_agent_callback` | `run_recorder` | run ledger for the UI without polluting prompts |
| `McpToolset` (stdio) | feedback store, filesystem | the agent's only path to data |
| `McpToolset` (Streamable HTTP) | GitHub | real external connector, secured by PAT header |
| `Runner` + sessions | FastAPI service | programmatic execution + SSE event stream |
| `get_fast_api_app` | `app/main.py` | one process serves ADK API + dashboard API + SPA |

## Security posture

- The model never touches the DB, filesystem, or GitHub directly — every effect passes an MCP
  tool boundary with explicit, narrow tools (`tool_filter` allow-lists on external servers).
- GitHub writes additionally pass the `action_guard` callback (directive-gated) and are
  ledgered with rationale + evidence ids.
- Secrets live in `.env` (never committed); the GitHub PAT is fine-grained to the demo repo.
