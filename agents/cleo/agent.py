"""Cleo — autonomous product-feedback operator (root ADK app, CONTRACTS §4).

Agent tree and why each ADK construct carries its weight:

    cleo_operator (LlmAgent — conversational operator & dispatcher)
    ├── triage_pipeline (SequentialAgent — one full triage pass)
    │     ingest_stage (ParallelAgent — concurrent source pulls via MCP)
    │     synthesizer  (LlmAgent — themes/tags; output_key="synthesis")
    │     prioritizer  (LlmAgent — output_schema=BetProposals; output_key="bets")
    │     actor        (LlmAgent — saves bets, guarded GitHub writes, brief)
    └── watch_loop (LoopAgent — continuous mode, max_iterations=3)
          triage_pipeline_w (same stages, fresh instances)

- **SequentialAgent** because triage has hard data dependencies: you cannot
  prioritize before synthesis exists. State flows stage-to-stage via
  ``output_key`` -> ``{placeholder}`` injection, not brittle prompt chaining.
- **ParallelAgent** because source ingestion is independent I/O — branches
  share nothing and write to the store idempotently.
- **LoopAgent** for "watch" mode: ingest_feedback dedupe makes every iteration
  idempotent, and the actor's ``exit_loop`` tool gives an escalation-stop when
  a pass finds no new signal. Two pipeline instances exist because ADK agents
  are single-parent and names must be unique tree-wide — hence the factories'
  ``suffix`` parameter.
- **Callbacks** (``run_starter``/``run_recorder`` here; ``action_guard`` on
  the actor) keep policy and audit in deterministic Python where the model
  cannot bypass them.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load repo-root .env BEFORE building agents: toolset composition (GitHub
# branch in/out) and model selection read the environment at import time.
# ``adk web`` loads .env itself, but uvicorn/pytest/Runner paths do not.
_REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_REPO_ROOT / ".env", override=False)

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent  # noqa: E402

from .callbacks import run_recorder, run_starter  # noqa: E402
from .sub_agents import (  # noqa: E402
    make_actor,
    make_ingest_stage,
    make_prioritizer,
    make_synthesizer,
)
from .toolsets import make_store_toolset  # noqa: E402


def make_triage_pipeline(suffix: str = "") -> SequentialAgent:
    """One full triage pass: ingest -> synthesize -> prioritize -> act.

    ``run_starter``/``run_recorder`` bracket the pass so every run — whether
    triggered from the UI, adk web, or the watch loop — lands in the ``runs``
    ledger with real before/after counts.
    """
    return SequentialAgent(
        name=f"triage_pipeline{suffix}",
        description=(
            "Runs one full feedback triage: pulls all sources in parallel, "
            "clusters themes, proposes structured bets, then acts on them "
            "(saves bets, escalates urgent issues to GitHub under directive, "
            "updates the product brief)."
        ),
        sub_agents=[
            make_ingest_stage(suffix),
            make_synthesizer(suffix),
            make_prioritizer(suffix),
            make_actor(suffix),
        ],
        before_agent_callback=run_starter,
        after_agent_callback=run_recorder,
    )


triage_pipeline = make_triage_pipeline()

# Suffix "_w" is load-bearing: run_starter detects it to record trigger="loop".
watch_loop = LoopAgent(
    name="watch_loop",
    description=(
        "Continuous watch mode: repeats the triage pipeline up to 3 times; "
        "the actor exits the loop early when a pass finds no new signal."
    ),
    sub_agents=[make_triage_pipeline("_w")],
    max_iterations=3,
)

cleo_operator = LlmAgent(
    name="cleo_operator",
    model=os.environ.get("CLEO_MODEL", "gemini-3.5-flash"),
    description=(
        "Cleo, the autonomous product-feedback operator: answers questions "
        "about the current product-feedback state and dispatches triage runs."
    ),
    instruction="""You are Cleo, an autonomous product-feedback operator for a startup team.
You sit on top of a feedback store (SQLite, reached only through MCP tools) that
holds: feedback items (fb_), themes (th_), bets (bet_), an action ledger (act_),
weekly briefs (br_), standing directives (dir_) and run records.

Answering questions — use your read tools, then answer concisely with ids and
evidence counts:
- `list_feedback` / `search_feedback` for raw feedback (filter by source, untriaged).
- `list_themes` for clusters and urgency; `list_bets` for proposed bets.
- `list_actions` for what Cleo has done autonomously (the audit ledger).
- `get_latest_brief` for the current product brief; `get_directives` for the
  active standing orders you operate under.
Never invent ids or counts — if a tool returns nothing, say so.

Delegating work — you do NOT triage yourself:
- When asked to "run", "triage", "process new feedback", or anything that
  requires re-reading sources and updating themes/bets, transfer to
  `triage_pipeline` (one full pass).
- When asked to "watch", "keep monitoring", or run "continuously", transfer to
  `watch_loop` (up to 3 passes, stops early when nothing new).

Directives are the user's declarative intent. If a user statement sounds like a
new standing order (contains "always", "from now on", "whenever"), tell them to
add it on the Directives page — you cannot create directives yourself.""",
    tools=[
        make_store_toolset(
            [
                "list_feedback",
                "search_feedback",
                "list_themes",
                "list_bets",
                "list_actions",
                "get_latest_brief",
                "get_directives",
            ]
        )
    ],
    sub_agents=[triage_pipeline, watch_loop],
)

# ADK's loader contract: the app's entry agent must be exposed as
# ``root_agent`` in ``<agents_dir>/<app_name>/agent.py``.
root_agent = cleo_operator
