"""Actor: the stage that ACTS — saves bets, escalates to GitHub, writes the brief.

This is where declarative intent becomes real-world side effects, so it is the
only agent holding GitHub WRITE tools, and those tools sit behind the
``action_guard`` ``before_tool_callback`` (deterministic policy: active
"escalate" directive + GITHUB_DEMO_REPO target + cited fb_ evidence, else the
call is skipped and ledgered). The paired ``after_tool_callback`` completes
the ledger entry with the real result — the model never writes its own audit
trail for GitHub actions.

It also carries ADK's ``exit_loop`` tool: inside ``watch_loop`` the actor ends
the loop early when a pass produced nothing new (escalation-stop semantics);
in a single pipeline run the exit simply ends the final stage, harmless.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent
from ..model import cleo_model
from ..skills_index import render_skills_index
from google.adk.tools import exit_loop

from ..callbacks import action_guard, record_github_write_result
from ..toolsets import make_github_toolset, make_store_toolset


def make_actor(suffix: str = "") -> LlmAgent:
    github_toolset = make_github_toolset(read_only=False)
    demo_repo = os.environ.get("GITHUB_DEMO_REPO", "").strip()
    if github_toolset is not None and "/" in demo_repo:
        owner, repo_name = demo_repo.split("/", 1)
        github_guidance = f"""Step 3 — escalate if, and only if, an ACTIVE directive mentions escalating AND at
least one bet or theme has urgency >= 2. For the SINGLE most urgent issue, call
`create_issue` with owner="{owner}", repo="{repo_name}":
- title: `[Cleo] <theme title>`
- body (markdown): a short problem statement, an `## Evidence` section quoting
  2-3 feedback items each with its fb_ id verbatim, an `## Impact` line
  (urgency, churn risk), and `_Filed autonomously by Cleo under directive._`
A policy guard reviews every GitHub write. If it returns status "blocked", do
NOT retry or rephrase — the block plus its reasons are already in the action
ledger. The guard also records every allowed write, so never call
`record_action` yourself for GitHub actions (it would double-count)."""
    else:
        github_guidance = """Step 3 — GitHub is not configured in this environment, so escalation is
impossible. If a directive demanded escalation for an urgency >= 2 issue, call
`record_action` ONCE with {"type": "escalation", "status": "skipped",
"target": "github (unconfigured)", "rationale": "<why it deserved escalation>",
"evidence_ids": ["fb_..."]} so the need is still on the ledger."""

    tools = [
        make_store_toolset(
            [
                "save_bets",
                "get_directives",
                "record_action",
                "write_brief",
                "get_latest_brief",
                "list_skills",
                "load_skill",
                "save_skill",
            ]
        ),
        exit_loop,
    ]
    if github_toolset is not None:
        tools.insert(1, github_toolset)

    return LlmAgent(
        name=f"actor{suffix}",
        model=cleo_model(),
        description=(
            "Persists the bets, escalates urgent issues to GitHub under directive, "
            "and keeps the weekly brief current."
        ),
        instruction=f"""You are Cleo's actor. The prioritizer produced these bet proposals (from shared state):

{{bets?}}

The synthesis report behind them:

{{synthesis?}}

Execute, in order:

Step 1 — call `save_bets` ONCE with the bets list exactly as proposed (the
store assigns bet_ ids and status "proposed"). If the bets state above is
empty, skip to Step 2.

Step 2 — call `get_directives`. The ACTIVE directives are your standing
orders; quote the directive you are acting under whenever you take an action.

{github_guidance}

Step 4 — if a directive asks to keep the product brief current, call
`write_brief` ONCE with theme_ids from the synthesis and markdown:
`# Product Brief — <ISO week>` then `## Urgent` (urgency >= 2 themes, one line
each with evidence count), `## Top Themes`, `## Proposed Bets` (title,
impact/effort/confidence, evidence_ids), `## Actions Taken` (GitHub issues
filed or blocked this run). Then call `record_action` ONCE with
{{"type": "brief", "status": "executed", "target": "<the br_ id returned>",
"rationale": "directive: keep the weekly brief current",
"evidence_ids": []}}.

Step 5 — reply with a 3-5 line run summary: bets saved, escalations
filed/blocked/skipped (with reasons), brief id. If this run produced no new
bets AND no actions, call `exit_loop` and reply `no new signal — watch loop done.`"""
        + "\n\n"
        + render_skills_index(),
        tools=tools,
        before_tool_callback=action_guard,
        after_tool_callback=record_github_write_result,
    )
