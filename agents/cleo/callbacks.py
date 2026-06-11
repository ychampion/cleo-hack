"""ADK callbacks: autonomy guardrails + run ledger (CONTRACTS §4).

Two concerns live here, both implemented as ADK callbacks because callbacks
are deterministic Python that the model cannot talk its way around:

- ``action_guard`` (``before_tool_callback`` on the actor): policy gate for
  GitHub WRITE tools. Returning a dict from a before_tool_callback makes ADK
  SKIP the real tool call and feed that dict back to the model as the tool
  result — i.e. a genuine block, not a prompt suggestion.
- ``run_starter`` / ``run_recorder`` (``before/after_agent_callback`` on the
  triage pipeline): bracket every pipeline run with a ``runs`` row so the UI
  ledger shows what each run ingested/produced.

LEDGER DESIGN CHOICE (documented per CONTRACTS §4): callbacks write to the
store DIRECTLY via ``mcp_server.store.Store`` instead of calling the
``record_action`` MCP tool. Callbacks are synchronous policy code running in
the server process; routing their audit writes through the LLM's own MCP
session would (a) require an async MCP round-trip mid-callback and (b) let a
confused model skip the recording. Direct writes make the ledger unforgeable
by the model: every allowed GitHub write is recorded (proposed -> executed via
the after_tool_callback) and every blocked one is recorded as ``skipped``.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from .toolsets import db_path

# Tool names (CONTRACTS §3 tool_filter) that mutate the outside world.
GITHUB_WRITE_TOOL_NAMES = {"create_issue", "add_issue_comment"}

# Session-state keys used to pass ids between paired callbacks. Namespaced
# with "cleo_" and never referenced in instruction templates, so ADK's
# {placeholder} injection can never collide with them.
_PENDING_ACTION_KEY = "cleo_pending_action_id"
_RUN_ID_KEY = "cleo_run_id"
_RUN_BASELINE_KEY = "cleo_run_baseline"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _open_store():
    """Open the shared SQLite store, or None if mcp_server isn't built yet.

    Lazy import so the agents package stays importable while ``mcp_server/``
    is still being developed in parallel; the guard FAILS CLOSED (blocks
    GitHub writes) when the store is unavailable.
    """
    try:
        from mcp_server.store import Store  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - missing parallel component
        print(f"[cleo.callbacks] store unavailable: {exc}", file=sys.stderr)
        return None
    return Store(str(db_path()))


def _rows(store: Any, collection: str) -> list[dict]:
    """Normalize Store.list() output to payload dicts (defensive: the store
    is owned by another component; tolerate either payload dicts or
    row wrappers with a 'payload' field)."""
    out = []
    for row in store.list(collection) or []:
        if isinstance(row, dict) and "payload" in row and "id" not in row:
            payload = row["payload"]
            row = json.loads(payload) if isinstance(payload, str) else payload
        if isinstance(row, dict):
            out.append(row)
    return out


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return {"repr": repr(value)[:2000]}


def _has_active_escalation_directive(store: Any) -> bool:
    """True iff an ACTIVE directive authorizes escalation.

    This is the declarative-intent check: autonomy comes from a standing
    directive the human wrote, not from the model deciding it may act.
    """
    for d in _rows(store, "directives"):
        if d.get("active") and "escalat" in str(d.get("text", "")).lower():
            return True
    return False


def _record_action(store: Any, action: dict) -> str:
    act_id = _new_id("act")
    doc = {
        "id": act_id,
        "type": action.get("type", "escalation"),
        "status": action.get("status", "proposed"),
        "target": action.get("target", ""),
        "payload": action.get("payload", {}),
        "rationale": action.get("rationale", ""),
        "evidence_ids": action.get("evidence_ids", []),
        "created_at": _now(),
        "executed_at": action.get("executed_at"),
        "result": action.get("result", {}),
    }
    store.put("actions", act_id, doc)
    return act_id


def _extract_evidence_ids(text: str) -> list[str]:
    import re  # noqa: PLC0415

    return sorted(set(re.findall(r"\bfb_[0-9a-f]{6,}\b", text)))


def action_guard(tool, args, tool_context):
    """before_tool_callback: gate GitHub write tools behind real policy.

    A GitHub write is allowed only when ALL hold:
      1. an ACTIVE directive containing "escalate" exists in the store
         (declarative authorization),
      2. the target repo equals ``GITHUB_DEMO_REPO`` exactly (blast-radius
         containment — Cleo can never write to an arbitrary repo),
      3. the body carries an evidence section citing at least one ``fb_`` id
         (accountability — no evidence, no action).

    Allowed writes are pre-recorded in the actions ledger as ``proposed``
    (completed to ``executed`` by ``record_github_write_result``); blocked
    writes are recorded as ``skipped`` with the reasons, then the block dict
    is returned so ADK skips the tool and the model sees WHY it was refused.
    """
    if tool.name not in GITHUB_WRITE_TOOL_NAMES:
        return None  # not a write: let it through untouched

    store = _open_store()
    body = str(args.get("body", "") or "")
    title = str(args.get("title", "") or "")
    target = f"{args.get('owner', '')}/{args.get('repo', '')}"
    demo_repo = os.environ.get("GITHUB_DEMO_REPO", "").strip()
    evidence_ids = _extract_evidence_ids(body)

    reasons: list[str] = []
    if store is None:
        reasons.append("feedback store unavailable; cannot verify directives")
    elif not _has_active_escalation_directive(store):
        reasons.append("no active directive authorizes escalation")
    if not demo_repo:
        reasons.append("GITHUB_DEMO_REPO is not configured")
    elif target.lower() != demo_repo.lower():
        reasons.append(f"target {target!r} is not the authorized repo {demo_repo!r}")
    if "evidence" not in body.lower() or not evidence_ids:
        reasons.append("body lacks an Evidence section citing fb_ ids")

    if reasons:
        if store is not None:
            _record_action(
                store,
                {
                    "type": "github_issue" if tool.name == "create_issue" else "github_comment",
                    "status": "skipped",
                    "target": target,
                    "payload": {"title": title, "tool": tool.name},
                    "rationale": "blocked by action_guard: " + "; ".join(reasons),
                    "evidence_ids": evidence_ids,
                },
            )
        return {
            "status": "blocked",
            "tool": tool.name,
            "reasons": reasons,
            "hint": (
                "GitHub writes require an active 'escalate' directive, the "
                "GITHUB_DEMO_REPO target, and an Evidence section citing fb_ ids."
            ),
        }

    act_id = _record_action(
        store,
        {
            "type": "github_issue" if tool.name == "create_issue" else "github_comment",
            "status": "proposed",
            "target": target,
            "payload": {"title": title, "tool": tool.name, "args": _jsonable(dict(args))},
            "rationale": "authorized by active escalation directive",
            "evidence_ids": evidence_ids,
        },
    )
    tool_context.state[_PENDING_ACTION_KEY] = act_id
    return None  # authorized: ADK proceeds with the real tool call


def record_github_write_result(tool, args, tool_context, tool_response):
    """after_tool_callback: complete the ledger entry for an executed write."""
    if tool.name not in GITHUB_WRITE_TOOL_NAMES:
        return None
    act_id = tool_context.state.get(_PENDING_ACTION_KEY)
    if not act_id:
        return None  # the write was blocked (no pending entry)
    store = _open_store()
    if store is None:
        return None
    doc = store.get("actions", act_id)
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, dict):
        return None
    failed = isinstance(tool_response, dict) and (
        tool_response.get("isError") or tool_response.get("status") == "error"
    )
    doc["status"] = "failed" if failed else "executed"
    doc["executed_at"] = _now()
    doc["result"] = _jsonable(tool_response)
    store.put("actions", act_id, doc)
    tool_context.state[_PENDING_ACTION_KEY] = None
    return None  # never alter the tool response the model sees


def _counts(store: Any) -> dict[str, int]:
    return {
        "feedback": len(_rows(store, "feedback")),
        "themes": len(_rows(store, "themes")),
        "bets": len(_rows(store, "bets")),
        "actions": len(_rows(store, "actions")),
    }


def run_starter(callback_context):
    """before_agent_callback on the triage pipeline: open the run ledger row.

    If the UI already created a ``running`` row via POST /api/agent/run we
    adopt it (so the UI's run_id and ours match); otherwise (adk web / Runner)
    we create one. A baseline snapshot of store counts lets run_recorder
    report true deltas instead of totals.
    """
    store = _open_store()
    if store is None:
        return None
    run_id = None
    runs = _rows(store, "runs")
    running = [r for r in runs if r.get("status") == "running"]
    if running:
        running.sort(key=lambda r: r.get("started_at", ""), reverse=True)
        run_id = running[0]["id"]
    else:
        run_id = _new_id("run")
        trigger = "loop" if callback_context.agent_name.endswith("_w") else "manual"
        store.put(
            "runs",
            run_id,
            {
                "id": run_id,
                "trigger": trigger,
                "started_at": _now(),
                "finished_at": None,
                "status": "running",
                "summary": "",
                "counts": {"ingested": 0, "themes": 0, "bets": 0, "actions": 0},
            },
        )
    callback_context.state[_RUN_ID_KEY] = run_id
    callback_context.state[_RUN_BASELINE_KEY] = _counts(store)
    return None  # never short-circuit the pipeline


def run_recorder(callback_context):
    """after_agent_callback on the triage pipeline: finish_run with counts."""
    store = _open_store()
    if store is None:
        return None
    run_id = callback_context.state.get(_RUN_ID_KEY)
    if not run_id:
        return None
    baseline = callback_context.state.get(_RUN_BASELINE_KEY) or {}
    now = _counts(store)
    counts = {
        "ingested": max(0, now["feedback"] - baseline.get("feedback", 0)),
        "themes": max(0, now["themes"] - baseline.get("themes", 0)),
        "bets": max(0, now["bets"] - baseline.get("bets", 0)),
        "actions": max(0, now["actions"] - baseline.get("actions", 0)),
    }
    doc = store.get("runs", run_id)
    if isinstance(doc, str):
        doc = json.loads(doc)
    if not isinstance(doc, dict):
        return None
    doc["status"] = "done"
    doc["finished_at"] = _now()
    doc["counts"] = counts
    doc["summary"] = (
        f"ingested {counts['ingested']} feedback, "
        f"{counts['themes']} new/updated themes, {counts['bets']} bets, "
        f"{counts['actions']} ledger actions"
    )
    store.put("runs", run_id, doc)
    callback_context.state[_RUN_ID_KEY] = None
    return None
