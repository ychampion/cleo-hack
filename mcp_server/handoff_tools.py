"""Handoff tools — bet -> coder work orders on the shared store (CONTRACTS §12).

Registered on the SAME FastMCP instance as the §2 tools: ``mcp_server.server``
imports this module at the bottom of its own import, so one ``python -m
mcp_server.server`` process serves both tool families. Like every §2 tool,
each function here is a plain importable function (the ``@mcp.tool()``
decorator returns it unchanged) returning a JSON-serializable dict with
``"status": "success" | "error"``.

Handoff shape (collection "handoffs"):
    {"id":"hf_…","bet_id":null|"bet_…","title":"…","problem":"…",
     "evidence_ids":[],"acceptance":["…"],"status":"open|in_progress|done|failed",
     "result":{"files_changed":[],"tests":"","notes":""},
     "created_at":"…","finished_at":null}
"""

from __future__ import annotations

from typing import Any

from mcp_server.server import _err, get_store, mcp
from mcp_server.store import new_id, utc_now

HANDOFF_STATUSES = ("open", "in_progress", "done", "failed")
TERMINAL_STATUSES = ("done", "failed")

_RESULT_DEFAULTS: dict[str, Any] = {"files_changed": [], "tests": "", "notes": ""}


def _normalize_result(result: Any, existing: dict | None = None) -> dict | None:
    """Merge a result dict over the existing one, guaranteeing the §12 keys.

    Returns None when ``result`` is not a dict (callers turn that into _err).
    Extra keys are preserved — the coder may attach more context than the
    contract minimum, and the UI renders result JSON verbatim.
    """
    if result is not None and not isinstance(result, dict):
        return None
    merged = {**_RESULT_DEFAULTS, **(existing or {}), **(result or {})}
    if not isinstance(merged.get("files_changed"), list):
        return None
    return merged


@mcp.tool()
def create_handoff(handoff: dict) -> dict:
    """Open a coder work order (handoff); status defaults to 'open'."""
    if not isinstance(handoff, dict):
        return _err("handoff must be a dict")
    title = handoff.get("title")
    if not isinstance(title, str) or not title.strip():
        return _err("handoff title is required and must be a non-empty string")
    status = handoff.get("status", "open")
    if status not in HANDOFF_STATUSES:
        return _err(f"handoff status must be one of {list(HANDOFF_STATUSES)}, got {status!r}")
    evidence_ids = handoff.get("evidence_ids", [])
    acceptance = handoff.get("acceptance", [])
    if not isinstance(evidence_ids, list) or not isinstance(acceptance, list):
        return _err("evidence_ids and acceptance must be lists")
    result = _normalize_result(handoff.get("result"))
    if result is None:
        return _err("result must be a dict with a files_changed list")
    handoff_id = handoff.get("id") or new_id("hf")
    now = utc_now()
    doc = {
        "id": handoff_id,
        "bet_id": handoff.get("bet_id"),
        "title": title.strip(),
        "problem": handoff.get("problem", ""),
        "evidence_ids": evidence_ids,
        "acceptance": acceptance,
        "status": status,
        "result": result,
        "created_at": handoff.get("created_at") or now,
        # Normally None at creation; set when a handoff is recorded already
        # terminal (e.g. backfilled history) so terminal == has finished_at.
        "finished_at": now if status in TERMINAL_STATUSES else None,
    }
    get_store().put("handoffs", handoff_id, doc)
    return {"status": "success", "id": handoff_id}


@mcp.tool()
def get_handoff(id: str) -> dict:
    """Return a single handoff by id."""
    doc = get_store().get("handoffs", id)
    if doc is None:
        return _err(f"handoff {id!r} not found")
    return {"status": "success", "handoff": doc}


@mcp.tool()
def list_handoffs(status: str = "") -> dict:
    """List handoffs, optionally filtered by status."""
    if status and status not in HANDOFF_STATUSES:
        return _err(f"status must be one of {list(HANDOFF_STATUSES)} or empty")
    filters = {"status": status} if status else {}
    return {"status": "success", "handoffs": get_store().list("handoffs", **filters)}


@mcp.tool()
def update_handoff(id: str, status: str, result: dict | None = None) -> dict:
    """Move a handoff to a new status; done/failed stamp finished_at and attach the result."""
    if status not in HANDOFF_STATUSES:
        return _err(f"status must be one of {list(HANDOFF_STATUSES)}, got {status!r}")
    store = get_store()
    doc = store.get("handoffs", id)
    if doc is None:
        return _err(f"handoff {id!r} not found")
    merged = _normalize_result(result, existing=doc.get("result"))
    if merged is None:
        return _err("result must be a dict with a files_changed list")
    doc["status"] = status
    doc["result"] = merged
    # Re-opening a terminal handoff clears the stamp so terminal <=> finished_at.
    doc["finished_at"] = utc_now() if status in TERMINAL_STATUSES else None
    store.put("handoffs", id, doc)
    return {"status": "success"}
