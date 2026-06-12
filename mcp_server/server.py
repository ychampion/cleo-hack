"""cleo-feedback-store — FastMCP stdio server owning the Cleo SQLite store (CONTRACTS §2).

Every tool is a plain importable function (the `@mcp.tool()` decorator returns it
unchanged), so tests and seed scripts call them directly without any MCP transport.
Every tool returns a JSON-serializable dict with "status": "success" | "error".

Launch: `uv run python -m mcp_server.server`
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.store import DEFAULT_DB_PATH, Store, new_id, utc_now

mcp = FastMCP("cleo-feedback-store")

FEEDBACK_SOURCES = ("github", "intercom", "slack", "call", "doc")
SENTIMENTS = ("pos", "neu", "neg")
THEME_TRENDS = ("new", "rising", "steady")
BET_STATUSES = ("proposed", "approved", "shipped")
ACTION_TYPES = ("github_issue", "github_comment", "brief", "escalation", "code_fix")
ACTION_STATUSES = ("proposed", "executed", "failed", "skipped")
COMPLETE_STATUSES = ("executed", "failed", "skipped")
RUN_TRIGGERS = ("manual", "loop")

_store: Store | None = None
_store_path: str | None = None


def get_store() -> Store:
    """Return the shared Store, re-opening it whenever CLEO_DB_PATH changes (test-friendly)."""
    global _store, _store_path
    path = os.environ.get("CLEO_DB_PATH") or DEFAULT_DB_PATH
    if _store is None or _store_path != path:
        if _store is not None:
            _store.close()
        _store = Store(path)
        _store_path = path
    return _store


def _err(message: str) -> dict[str, Any]:
    return {"status": "error", "message": message}


def _int_in_range(value: Any, lo: int, hi: int) -> int | None:
    """Coerce ints / integral floats within [lo, hi]; None when invalid."""
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and lo <= value <= hi:
        return value
    return None


def _current_week() -> str:
    """ISO week label like '2026-W24'."""
    iso = datetime.now(timezone.utc).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


# -- Feedback -----------------------------------------------------------------


@mcp.tool()
def ingest_feedback(items: list[dict]) -> dict:
    """Ingest raw feedback items into the store, deduplicating on (source, external_id)."""
    if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
        return _err("items must be a list of dicts")
    store = get_store()
    ingested = 0
    duplicates = 0
    seen: set[tuple[str, str]] = set()
    for idx, item in enumerate(items):
        source = item.get("source")
        if source not in FEEDBACK_SOURCES:
            return _err(
                f"item {idx}: source must be one of {list(FEEDBACK_SOURCES)}, got {source!r}"
            )
        text = item.get("text")
        if not isinstance(text, str) or not text.strip():
            return _err(f"item {idx}: text is required and must be a non-empty string")
        external_id = item.get("external_id")
        if external_id is not None:
            key = (source, str(external_id))
            if key in seen or store.list("feedback", source=source, external_id=external_id):
                duplicates += 1
                continue
            seen.add(key)
        now = utc_now()
        doc = {
            "id": item.get("id") or new_id("fb"),
            "source": source,
            "external_id": external_id,
            "author": item.get("author") or "unknown",
            "text": text,
            "url": item.get("url"),
            "created_at": item.get("created_at") or now,
            "ingested_at": now,
            "urgency": item.get("urgency"),
            "sentiment": item.get("sentiment"),
            "theme_id": item.get("theme_id"),
            "metadata": item.get("metadata") or {},
        }
        store.put("feedback", doc["id"], doc)
        ingested += 1
    return {"status": "success", "ingested": ingested, "duplicates": duplicates}


@mcp.tool()
def list_feedback(source: str = "", only_untriaged: bool = False, limit: int = 50) -> dict:
    """List feedback items, optionally filtered by source and/or untriaged (no theme) status."""
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return _err("limit must be a positive integer")
    if source and source not in FEEDBACK_SOURCES:
        return _err(f"source must be one of {list(FEEDBACK_SOURCES)} or empty, got {source!r}")
    filters: dict[str, Any] = {}
    if source:
        filters["source"] = source
    if only_untriaged:
        filters["theme_id"] = None
    items = get_store().list("feedback", limit=limit, **filters)
    return {"status": "success", "items": items}


@mcp.tool()
def search_feedback(query: str, limit: int = 20) -> dict:
    """Keyword-search feedback text and author (case-insensitive substring match)."""
    if not isinstance(query, str) or not query.strip():
        return _err("query must be a non-empty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        return _err("limit must be a positive integer")
    items = get_store().search_text(
        "feedback", query.strip(), fields=("text", "author"), limit=limit
    )
    return {"status": "success", "items": items}


@mcp.tool()
def tag_feedback(updates: list[dict]) -> dict:
    """Apply triage tags ({id, urgency?, sentiment?, theme_id?}) to existing feedback items."""
    if not isinstance(updates, list) or not all(isinstance(u, dict) for u in updates):
        return _err("updates must be a list of dicts")
    store = get_store()
    updated = 0
    for idx, update in enumerate(updates):
        fb_id = update.get("id")
        if not fb_id:
            return _err(f"update {idx}: id is required")
        doc = store.get("feedback", fb_id)
        if doc is None:
            return _err(f"update {idx}: feedback {fb_id!r} not found")
        if "urgency" in update:
            urgency = update["urgency"]
            if urgency is not None:
                urgency = _int_in_range(urgency, 0, 3)
                if urgency is None:
                    return _err(f"update {idx}: urgency must be an integer 0-3")
            doc["urgency"] = urgency
        if "sentiment" in update:
            sentiment = update["sentiment"]
            if sentiment is not None and sentiment not in SENTIMENTS:
                return _err(f"update {idx}: sentiment must be one of {list(SENTIMENTS)}")
            doc["sentiment"] = sentiment
        if "theme_id" in update:
            doc["theme_id"] = update["theme_id"]
        store.put("feedback", fb_id, doc)
        updated += 1
    return {"status": "success", "updated": updated}


# -- Themes ---------------------------------------------------------------------


@mcp.tool()
def save_themes(themes: list[dict]) -> dict:
    """Upsert feedback themes (clusters); assigns th_ ids when missing."""
    if not isinstance(themes, list) or not all(isinstance(t, dict) for t in themes):
        return _err("themes must be a list of dicts")
    store = get_store()
    ids: list[str] = []
    docs: list[dict[str, Any]] = []
    for idx, theme in enumerate(themes):
        theme_id = theme.get("id") or new_id("th")
        existing = store.get("themes", theme_id) or {}
        title = theme.get("title", existing.get("title"))
        if not isinstance(title, str) or not title.strip():
            return _err(f"theme {idx}: title is required and must be a non-empty string")
        urgency = theme.get("urgency", existing.get("urgency", 0))
        urgency = _int_in_range(urgency, 0, 3)
        if urgency is None:
            return _err(f"theme {idx}: urgency must be an integer 0-3")
        trend = theme.get("trend", existing.get("trend", "new"))
        if trend not in THEME_TRENDS:
            return _err(f"theme {idx}: trend must be one of {list(THEME_TRENDS)}")
        feedback_ids = theme.get("feedback_ids", existing.get("feedback_ids", []))
        if not isinstance(feedback_ids, list):
            return _err(f"theme {idx}: feedback_ids must be a list")
        now = utc_now()
        docs.append(
            {
                "id": theme_id,
                "title": title.strip(),
                "summary": theme.get("summary", existing.get("summary", "")),
                "urgency": urgency,
                "trend": trend,
                "feedback_ids": feedback_ids,
                "first_seen": theme.get("first_seen", existing.get("first_seen", now)),
                "last_seen": theme.get("last_seen", existing.get("last_seen", now)),
            }
        )
        ids.append(theme_id)
    for doc in docs:
        store.put("themes", doc["id"], doc)
    return {"status": "success", "saved": len(docs), "ids": ids}


@mcp.tool()
def list_themes() -> dict:
    """List all saved themes."""
    return {"status": "success", "themes": get_store().list("themes")}


# -- Bets ----------------------------------------------------------------------


@mcp.tool()
def save_bets(bets: list[dict]) -> dict:
    """Upsert evidence-backed product bets; assigns bet_ ids when missing."""
    if not isinstance(bets, list) or not all(isinstance(b, dict) for b in bets):
        return _err("bets must be a list of dicts")
    store = get_store()
    ids: list[str] = []
    docs: list[dict[str, Any]] = []
    for idx, bet in enumerate(bets):
        bet_id = bet.get("id") or new_id("bet")
        existing = store.get("bets", bet_id) or {}
        title = bet.get("title", existing.get("title"))
        if not isinstance(title, str) or not title.strip():
            return _err(f"bet {idx}: title is required and must be a non-empty string")
        impact = _int_in_range(bet.get("impact", existing.get("impact", 3)), 1, 5)
        effort = _int_in_range(bet.get("effort", existing.get("effort", 3)), 1, 5)
        if impact is None or effort is None:
            return _err(f"bet {idx}: impact and effort must be integers 1-5")
        confidence = bet.get("confidence", existing.get("confidence", 0.5))
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not (
            0.0 <= float(confidence) <= 1.0
        ):
            return _err(f"bet {idx}: confidence must be a number between 0.0 and 1.0")
        urgency = _int_in_range(bet.get("urgency", existing.get("urgency", 0)), 0, 3)
        if urgency is None:
            return _err(f"bet {idx}: urgency must be an integer 0-3")
        status = bet.get("status", existing.get("status", "proposed"))
        if status not in BET_STATUSES:
            return _err(f"bet {idx}: status must be one of {list(BET_STATUSES)}")
        theme_ids = bet.get("theme_ids", existing.get("theme_ids", []))
        evidence_ids = bet.get("evidence_ids", existing.get("evidence_ids", []))
        if not isinstance(theme_ids, list) or not isinstance(evidence_ids, list):
            return _err(f"bet {idx}: theme_ids and evidence_ids must be lists")
        docs.append(
            {
                "id": bet_id,
                "title": title.strip(),
                "problem": bet.get("problem", existing.get("problem", "")),
                "proposal": bet.get("proposal", existing.get("proposal", "")),
                "impact": impact,
                "effort": effort,
                "confidence": float(confidence),
                "urgency": urgency,
                "theme_ids": theme_ids,
                "evidence_ids": evidence_ids,
                "status": status,
                "created_at": existing.get("created_at") or bet.get("created_at") or utc_now(),
            }
        )
        ids.append(bet_id)
    for doc in docs:
        store.put("bets", doc["id"], doc)
    return {"status": "success", "saved": len(docs), "ids": ids}


@mcp.tool()
def list_bets() -> dict:
    """List all saved product bets."""
    return {"status": "success", "bets": get_store().list("bets")}


# -- Actions (autonomous-action ledger) -----------------------------------------


@mcp.tool()
def record_action(action: dict) -> dict:
    """Record an entry in the autonomous-action ledger; status defaults to 'proposed'."""
    if not isinstance(action, dict):
        return _err("action must be a dict")
    action_type = action.get("type")
    if action_type not in ACTION_TYPES:
        return _err(f"action type must be one of {list(ACTION_TYPES)}, got {action_type!r}")
    status = action.get("status", "proposed")
    if status not in ACTION_STATUSES:
        return _err(f"action status must be one of {list(ACTION_STATUSES)}")
    evidence_ids = action.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        return _err("evidence_ids must be a list")
    action_id = action.get("id") or new_id("act")
    doc = {
        "id": action_id,
        "type": action_type,
        "status": status,
        "target": action.get("target", ""),
        "payload": action.get("payload") or {},
        "rationale": action.get("rationale", ""),
        "evidence_ids": evidence_ids,
        "created_at": action.get("created_at") or utc_now(),
        "executed_at": action.get("executed_at"),
        "result": action.get("result") or {},
    }
    get_store().put("actions", action_id, doc)
    return {"status": "success", "id": action_id}


@mcp.tool()
def complete_action(id: str, status: str, result: dict | None = None) -> dict:
    """Mark a ledger action executed/failed/skipped and attach its result."""
    if status not in COMPLETE_STATUSES:
        return _err(f"status must be one of {list(COMPLETE_STATUSES)}, got {status!r}")
    store = get_store()
    doc = store.get("actions", id)
    if doc is None:
        return _err(f"action {id!r} not found")
    doc["status"] = status
    doc["executed_at"] = utc_now()
    doc["result"] = result or {}
    store.put("actions", id, doc)
    return {"status": "success"}


@mcp.tool()
def list_actions(status: str = "") -> dict:
    """List ledger actions, optionally filtered by status."""
    if status and status not in ACTION_STATUSES:
        return _err(f"status must be one of {list(ACTION_STATUSES)} or empty")
    filters = {"status": status} if status else {}
    return {"status": "success", "actions": get_store().list("actions", **filters)}


# -- Briefs ----------------------------------------------------------------------


@mcp.tool()
def write_brief(markdown: str, theme_ids: list[str] | None = None) -> dict:
    """Save the weekly product brief (markdown) for the current ISO week."""
    if not isinstance(markdown, str) or not markdown.strip():
        return _err("markdown must be a non-empty string")
    if theme_ids is not None and not isinstance(theme_ids, list):
        return _err("theme_ids must be a list of theme ids")
    brief_id = new_id("br")
    doc = {
        "id": brief_id,
        "week": _current_week(),
        "markdown": markdown,
        "theme_ids": theme_ids or [],
        "created_at": utc_now(),
    }
    get_store().put("briefs", brief_id, doc)
    return {"status": "success", "id": brief_id}


@mcp.tool()
def get_latest_brief() -> dict:
    """Return the most recently written brief, or null when none exists."""
    briefs = get_store().list("briefs")
    latest = max(briefs, key=lambda b: b.get("created_at", ""), default=None)
    return {"status": "success", "brief": latest}


# -- Directives -------------------------------------------------------------------


@mcp.tool()
def get_directives() -> dict:
    """Return all currently active standing directives."""
    return {"status": "success", "directives": get_store().list("directives", active=True)}


# -- Runs (agent run ledger) -------------------------------------------------------


@mcp.tool()
def start_run(trigger: str) -> dict:
    """Open an agent run ledger entry ('manual' or 'loop') and return its id."""
    if trigger not in RUN_TRIGGERS:
        return _err(f"trigger must be one of {list(RUN_TRIGGERS)}, got {trigger!r}")
    # Stale-run sweep: a crashed/interrupted pipeline never reaches finish_run
    # (e.g. quota exhaustion mid-stage), which would leave a "running" row in
    # the UI forever. Runs never overlap, so any prior running row is stale by
    # definition the moment a new run starts.
    store = get_store()
    for doc in store.list("runs"):
        if doc.get("status") == "running":
            doc["status"] = "error"
            doc["finished_at"] = utc_now()
            doc["summary"] = doc.get("summary") or "interrupted before completion (superseded by a newer run)"
            store.put("runs", doc["id"], doc)
    run_id = new_id("run")
    doc = {
        "id": run_id,
        "trigger": trigger,
        "started_at": utc_now(),
        "finished_at": None,
        "status": "running",
        "summary": "",
        "counts": {"ingested": 0, "themes": 0, "bets": 0, "actions": 0},
    }
    get_store().put("runs", run_id, doc)
    return {"status": "success", "id": run_id}


@mcp.tool()
def finish_run(id: str, summary: str, counts: dict | None = None) -> dict:
    """Close an agent run with a summary and ingested/themes/bets/actions counts."""
    store = get_store()
    doc = store.get("runs", id)
    if doc is None:
        return _err(f"run {id!r} not found")
    if counts is not None and not isinstance(counts, dict):
        return _err("counts must be a dict")
    doc["finished_at"] = utc_now()
    doc["status"] = "done"
    doc["summary"] = summary
    doc["counts"] = {**{"ingested": 0, "themes": 0, "bets": 0, "actions": 0}, **(counts or {})}
    store.put("runs", id, doc)
    return {"status": "success"}


@mcp.tool()
def get_overview() -> dict:
    """Read-only workspace overview: counts, urgent themes, latest brief week."""
    store = get_store()
    feedback = store.list("feedback")
    themes = store.list("themes")
    actions = store.list("actions")
    briefs = store.list("briefs")
    latest = max(briefs, key=lambda b: b.get("created_at") or "", default=None)
    return {
        "status": "success",
        "counts": {
            "feedback": len(feedback),
            "untriaged": sum(1 for f in feedback if f.get("urgency") is None),
            "themes": len(themes),
            "bets": len(store.list("bets")),
            "actions_executed": sum(1 for a in actions if a.get("status") == "executed"),
        },
        "urgent": [
            {"id": t["id"], "title": t.get("title", ""), "urgency": t.get("urgency", 0)}
            for t in themes
            if (t.get("urgency") or 0) >= 2
        ],
        "latest_brief_week": (latest or {}).get("week"),
    }


# Extension tool modules (CONTRACTS §11/§12) register their tools on the shared
# `mcp` instance at import time. Imported at the bottom so the symbols they need
# (`mcp`, `get_store`, `_err`) already exist on this module.
from mcp_server import handoff_tools as _handoff_tools  # noqa: E402,F401
from mcp_server import skill_tools as _skill_tools  # noqa: E402,F401


def main() -> None:
    """CLI entry (CONTRACTS §10): stdio for in-process agents, sse/streamable-http
    so any MCP-capable client (Claude Code, Cursor, Gemini CLI, …) can connect."""
    import argparse

    # Double-import trap: under `python -m mcp_server.server` this file executes
    # as `__main__`, while the extension modules (skill_tools / handoff_tools)
    # register their tools on the CANONICAL `mcp_server.server` module instance.
    # Always serve the canonical instance so the full toolset is exposed; when
    # this module already IS canonical (normal import, e.g. the cleo CLI), the
    # self-import is a no-op returning the same object.
    from mcp_server.server import mcp as server_mcp

    parser = argparse.ArgumentParser(description="cleo-feedback-store MCP server")
    parser.add_argument("--transport", choices=("stdio", "sse", "streamable-http"), default="stdio")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    if args.transport != "stdio":
        server_mcp.settings.host = args.host
        server_mcp.settings.port = args.port
    server_mcp.run(transport=args.transport)


if __name__ == "__main__":
    main()
