"""Idempotent seeder: loads seed/corpus into the store via ingest_feedback (CONTRACTS §7).

No LLM, no MCP transport — calls the plain tool functions / Store directly.
Transcripts become one feedback item per customer speaker turn; docs become one
item per `## ` section. Re-running is a no-op thanks to (source, external_id) dedupe
and deterministic directive ids.

Run: `uv run python -m seed.seed`
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp_server.server import get_store, ingest_feedback
from mcp_server.store import utc_now

# Turn lines look like: **Dan Porter (Acme Robotics):** text...
_TURN_RE = re.compile(r"^\*\*(?P<speaker>[^*]+?):\*\*\s*(?P<text>\S.*)$")
_HEADER_RE = re.compile(r"^(?P<key>Date|Account|Owner):\s*(?P<value>.+)$")


def corpus_dir() -> Path:
    """Corpus location: $CORPUS_DIR if set, else seed/corpus next to this file."""
    env = os.environ.get("CORPUS_DIR")
    return Path(env) if env else Path(__file__).resolve().parent / "corpus"


def _epoch_to_iso(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_headers(lines: list[str]) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in lines:
        match = _HEADER_RE.match(line.strip())
        if match:
            headers[match.group("key").lower()] = match.group("value").strip()
    return headers


def load_slack_items(corpus: Path) -> list[dict[str, Any]]:
    """One feedback item per Slack message; external_id is the Slack ts."""
    data = json.loads((corpus / "slack-export.json").read_text(encoding="utf-8"))
    channel = data.get("channel", "#feedback")
    items = []
    for msg in data["messages"]:
        profile = msg.get("user_profile", {})
        items.append(
            {
                "source": "slack",
                "external_id": f"slack-{msg['ts']}",
                "author": profile.get("real_name") or msg.get("user", "unknown"),
                "text": msg["text"],
                "url": None,
                "created_at": _epoch_to_iso(msg["ts"]),
                "metadata": {"channel": channel, "team": profile.get("team")},
            }
        )
    return items


def load_ticket_items(corpus: Path) -> list[dict[str, Any]]:
    """One feedback item per support ticket (source 'intercom')."""
    tickets = json.loads((corpus / "tickets.json").read_text(encoding="utf-8"))
    items = []
    for ticket in tickets:
        items.append(
            {
                "source": "intercom",
                "external_id": ticket["id"],
                "author": ticket.get("requester", "unknown"),
                "text": f"{ticket['subject']}\n\n{ticket['body']}",
                "url": None,
                "created_at": ticket["created_at"],
                "metadata": {
                    "priority": ticket.get("priority"),
                    "tags": ticket.get("tags", []),
                },
            }
        )
    return items


def load_call_items(corpus: Path) -> list[dict[str, Any]]:
    """One feedback item per customer speaker turn; Lumen-side turns are skipped."""
    items = []
    for path in sorted((corpus / "call-transcripts").glob("*.md")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), path.stem)
        headers = _parse_headers(lines[:12])
        date = headers.get("date", "2026-06-01")
        account = headers.get("account", "unknown")
        turn_idx = 0
        for line in lines:
            match = _TURN_RE.match(line.strip())
            if not match:
                continue
            speaker = match.group("speaker").strip()
            if "(Lumen" in speaker:
                continue
            turn_idx += 1
            items.append(
                {
                    "source": "call",
                    "external_id": f"{path.stem}#t{turn_idx}",
                    "author": speaker,
                    "text": match.group("text").strip(),
                    "url": None,
                    "created_at": f"{date}T16:00:00Z",
                    "metadata": {"call": title, "account": account},
                }
            )
    return items


def load_doc_items(corpus: Path) -> list[dict[str, Any]]:
    """One feedback item per `## ` doc section; 'Respondent:' overrides the doc owner as author."""
    items = []
    for path in sorted((corpus / "docs").glob("*.md")):
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), path.stem)
        preamble = text.split("\n## ", 1)[0]
        headers = _parse_headers(preamble.splitlines())
        date = headers.get("date", "2026-06-01")
        owner = headers.get("owner", "unknown")
        sections = text.split("\n## ")[1:]
        for idx, section in enumerate(sections, start=1):
            heading, _, body = section.partition("\n")
            body = body.strip()
            author = owner
            respondent = re.search(r"^Respondent:\s*(.+)$", body, flags=re.MULTILINE)
            if respondent:
                author = respondent.group(1).strip()
                body = re.sub(r"^Respondent:.*\n?", "", body, flags=re.MULTILINE).strip()
            items.append(
                {
                    "source": "doc",
                    "external_id": f"{path.stem}#s{idx}",
                    "author": author,
                    "text": f"{heading.strip()}\n\n{body}",
                    "url": None,
                    "created_at": f"{date}T12:00:00Z",
                    "metadata": {"doc": title, "section": heading.strip()},
                }
            )
    return items


def build_items(corpus: Path | None = None) -> list[dict[str, Any]]:
    """All corpus feedback items in CONTRACTS §1 ingest shape."""
    corpus = corpus or corpus_dir()
    return (
        load_slack_items(corpus)
        + load_ticket_items(corpus)
        + load_call_items(corpus)
        + load_doc_items(corpus)
    )


def _directive_id(key: str) -> str:
    """Deterministic dir_<12 hex> id so re-seeding upserts instead of duplicating."""
    return f"dir_{hashlib.sha1(key.encode()).hexdigest()[:12]}"


def seed_directives() -> list[dict[str, Any]]:
    """Upsert the two standing directives from CONTRACTS §7 (idempotent)."""
    repo = os.environ.get("GITHUB_DEMO_REPO") or "the demo repo"
    directives = [
        (
            "cleo-directive-escalate",
            "Triage all new feedback daily: cluster it into themes, tag urgency and "
            f"sentiment, and escalate urgent churn risks as GitHub issues in {repo} "
            "with evidence links.",
        ),
        (
            "cleo-directive-brief",
            "Keep the weekly product brief current; rewrite it whenever themes or "
            "priorities change materially.",
        ),
    ]
    store = get_store()
    saved = []
    for key, text in directives:
        dir_id = _directive_id(key)
        existing = store.get("directives", dir_id)
        doc = {
            "id": dir_id,
            "text": text,
            "active": True if existing is None else existing.get("active", True),
            "created_at": (existing or {}).get("created_at") or utc_now(),
        }
        store.put("directives", dir_id, doc)
        saved.append(doc)
    return saved


def main() -> dict[str, Any]:
    """Seed the store from the corpus; safe to run repeatedly."""
    items = build_items()
    result = ingest_feedback(items)
    if result["status"] != "success":
        raise SystemExit(f"seed failed: {result.get('message')}")
    directives = seed_directives()
    store = get_store()
    summary = {
        "corpus_items": len(items),
        "ingested": result["ingested"],
        "duplicates": result["duplicates"],
        "feedback_total": store.count("feedback"),
        "directives": len(directives),
        "db_path": str(store.db_path),
    }
    print(
        f"seeded {summary['ingested']} new feedback items "
        f"({summary['duplicates']} duplicates skipped) from {summary['corpus_items']} corpus items; "
        f"{summary['feedback_total']} total in store; "
        f"{summary['directives']} directives active; db={summary['db_path']}"
    )
    return summary


if __name__ == "__main__":
    main()
