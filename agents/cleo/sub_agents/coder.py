"""Coder: the sub-agent that turns a handoff into a verified code fix (§12).

Agent-orchestrating-agents: the operator opens a handoff (a work order with
problem, evidence and acceptance criteria) and transfers here. The coder's
write surface is the in-process sandboxed FunctionTools in ``coder_tools``
(workspace/ only — the model cannot route around a path check that lives in
Python), while its store access is the same least-privilege MCP toolset
pattern every other stage uses, filtered to exactly the three tools the
handoff lifecycle needs.

The objective function is deterministic: ``run_workspace_tests`` is the only
judge of "fixed". The instruction caps fix attempts at 3 so a wrong theory
fails the handoff honestly instead of burning quota thrashing.
"""

from __future__ import annotations

import subprocess

from google.adk.agents import LlmAgent

from ..coder_tools import (
    REPO_ROOT,
    list_workspace,
    read_workspace_file,
    run_workspace_tests,
    write_workspace_file,
)
from ..model import cleo_model
from ..toolsets import make_store_toolset


def close_handoff_guard(callback_context):
    """after_agent_callback: enforce the handoff bookkeeping invariant in code.

    Flash-tier models sometimes skip the `update_handoff` protocol step even
    when instructed (observed live: green tests, ledgered code_fix, handoff
    left "open"). The ledger must reflect ground truth regardless of model
    diligence, so this guard closes the handoff FROM ground truth: the actual
    workspace test result and the actual git diff — the same philosophy as
    `action_guard` (invariants live in the harness, not in hope).
    """
    handoff_id = (callback_context.state.get("handoff_id") or "").strip()
    if not handoff_id:
        return None
    from mcp_server.handoff_tools import get_handoff, update_handoff  # in-process, same store

    found = get_handoff(handoff_id)
    if found.get("status") != "success":
        return None
    if found["handoff"]["status"] in ("done", "failed"):
        return None  # the agent did its bookkeeping; nothing to enforce

    tests = run_workspace_tests()
    green = tests.get("status") == "success" and tests.get("failed") == 0
    try:
        porcelain = subprocess.run(
            ["git", "status", "--porcelain", "--", "workspace/"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=15,
        ).stdout
        files_changed = [line[3:].strip() for line in porcelain.splitlines() if line.strip()]
    except Exception:
        files_changed = []
    update_handoff(
        handoff_id,
        "done" if green else "failed",
        {
            "files_changed": files_changed,
            "tests": f"{tests.get('passed', '?')}/{tests.get('failed', '?')}",
            "notes": "closed by runtime bookkeeping guard (agent omitted update_handoff); "
            "status derived from the actual workspace test run",
        },
    )
    return None


def make_coder(suffix: str = "") -> LlmAgent:
    return LlmAgent(
        name=f"coder{suffix}",
        model=cleo_model(),
        description=(
            "Fixes code in the demo workspace from a handoff: reads the work "
            "order, makes the smallest change that satisfies its acceptance "
            "criteria, and proves it by running the workspace test suite."
        ),
        instruction="""You are Cleo's coder. You work ONE handoff (a work order: problem,
evidence, acceptance criteria) to completion. The handoff id is in the
conversation that brought you here, or in session state: {handoff_id?}
If you cannot find a handoff id in either place, ask for it and stop.

Hard rules:
- You can only touch files under workspace/ — your tools enforce this; do not
  try to escape it.
- NEVER edit test files to make them pass. Tests are the acceptance criteria,
  not the bug. The fix always lives in application code.
- Make the SMALLEST change that satisfies the acceptance criteria. No
  refactors, no style cleanups, no drive-by improvements.

Procedure, in order:

1. Call `get_handoff` with the handoff id. Read problem + acceptance closely.
   If the handoff is missing or already done/failed, say so and stop.
2. Call `update_handoff(id, "in_progress")`, then `run_workspace_tests` ONCE
   to record the baseline failures.
3. Call `list_workspace`, then `read_workspace_file` on the files the failures
   point at. Reason from the actual code, not from guesses.
4. Apply your fix with `write_workspace_file` (full file content), then
   `run_workspace_tests` again. You have AT MOST 3 fix attempts
   (write + test = one attempt). If the suite is still failing after the 3rd
   attempt, call `update_handoff(id, "failed", result)` with honest notes on
   what you tried and what you believe is wrong, then report and stop.
5. When the suite is green (0 failed), call `update_handoff(id, "done",
   result)` with result = {"files_changed": [<workspace-relative paths you
   wrote>], "tests": "<passed>/<failed> from the final run", "notes":
   "<one-line root cause + fix>"}.
6. Call `record_action` ONCE with {"type": "code_fix", "status": "executed",
   "target": "<handoff id>", "rationale": "<root cause and why this fix
   satisfies the acceptance criteria>", "evidence_ids": <the handoff's
   evidence_ids>, "result": {"files_changed": ..., "tests": ...}}.
7. Reply with a 3-4 line summary: root cause, the change, final test counts,
   handoff status.

COMPLETION CONTRACT — read this before replying. Your work does not count until
the handoff record itself is closed. Immediately before writing your final
summary, call `get_handoff` one last time and check its status:
- status "done" or "failed" → you may reply.
- anything else (e.g. still "open" or "in_progress") → you skipped step 5; call
  `update_handoff` NOW with the proper terminal status and result, verify with
  `get_handoff` again, and only then reply.
A green test suite with an unclosed handoff is a FAILED run for you.""",
        tools=[
            list_workspace,
            read_workspace_file,
            write_workspace_file,
            run_workspace_tests,
            make_store_toolset(["get_handoff", "update_handoff", "record_action"]),
        ],
        after_agent_callback=close_handoff_guard,
    )
