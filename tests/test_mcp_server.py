"""MCP tool tests: each tool called directly as a plain Python function (CONTRACTS §2/§9)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server import server as srv  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point every test at a fresh tmp SQLite db; get_store() re-opens on path change."""
    monkeypatch.setenv("CLEO_DB_PATH", str(tmp_path / "cleo.db"))
    yield


def make_item(n: int = 1, **overrides) -> dict:
    item = {
        "source": "slack",
        "external_id": f"msg-{n}",
        "author": f"user{n}",
        "text": f"feedback number {n} about checkout",
    }
    item.update(overrides)
    return item


def ingest_one(**overrides) -> str:
    assert srv.ingest_feedback([make_item(**overrides)])["status"] == "success"
    return srv.list_feedback()["items"][-1]["id"]


def test_all_contract_tools_are_registered():
    expected = {
        "ingest_feedback", "list_feedback", "search_feedback", "tag_feedback",
        "save_themes", "list_themes", "save_bets", "list_bets",
        "record_action", "complete_action", "list_actions",
        "write_brief", "get_latest_brief", "get_directives",
        "start_run", "finish_run",
    }
    import asyncio

    registered = {t.name for t in asyncio.run(srv.mcp.list_tools())}
    assert expected <= registered


# -- ingest_feedback / list_feedback / search_feedback ---------------------------


def test_ingest_feedback_happy_path():
    result = srv.ingest_feedback([make_item(1), make_item(2, source="intercom")])
    assert result == {"status": "success", "ingested": 2, "duplicates": 0}
    items = srv.list_feedback()["items"]
    assert len(items) == 2
    fb = items[0]
    assert re.fullmatch(r"fb_[0-9a-f]{12}", fb["id"])
    # Full §1 shape with defaults filled in.
    for key in ("source", "external_id", "author", "text", "url", "created_at",
                "ingested_at", "urgency", "sentiment", "theme_id", "metadata"):
        assert key in fb
    assert fb["urgency"] is None and fb["theme_id"] is None


def test_ingest_feedback_dedupes_on_source_and_external_id():
    assert srv.ingest_feedback([make_item(1)])["ingested"] == 1
    again = srv.ingest_feedback([make_item(1), make_item(1)])  # dup vs store AND within batch
    assert again == {"status": "success", "ingested": 0, "duplicates": 2}
    # Same external_id but different source is NOT a duplicate.
    assert srv.ingest_feedback([make_item(1, source="intercom")])["ingested"] == 1


def test_ingest_feedback_rejects_bad_source():
    result = srv.ingest_feedback([make_item(1, source="carrier-pigeon")])
    assert result["status"] == "error"
    assert "source" in result["message"]


def test_ingest_feedback_rejects_missing_text_and_non_list():
    assert srv.ingest_feedback([{"source": "slack", "text": "  "}])["status"] == "error"
    assert srv.ingest_feedback("not a list")["status"] == "error"


def test_list_feedback_filters():
    srv.ingest_feedback([make_item(1), make_item(2, source="doc")])
    fb_id = srv.list_feedback(source="slack")["items"][0]["id"]
    srv.tag_feedback([{"id": fb_id, "theme_id": "th_x"}])
    assert len(srv.list_feedback()["items"]) == 2
    assert len(srv.list_feedback(source="doc")["items"]) == 1
    untriaged = srv.list_feedback(only_untriaged=True)["items"]
    assert [i["source"] for i in untriaged] == ["doc"]
    assert len(srv.list_feedback(limit=1)["items"]) == 1


def test_list_feedback_rejects_bad_args():
    assert srv.list_feedback(limit=0)["status"] == "error"
    assert srv.list_feedback(source="telegraph")["status"] == "error"


def test_search_feedback():
    srv.ingest_feedback([
        make_item(1, text="the checkout page 500s on submit"),
        make_item(2, text="please add CSV export"),
    ])
    hits = srv.search_feedback("CHECKOUT")["items"]
    assert len(hits) == 1 and "checkout" in hits[0]["text"]
    assert srv.search_feedback("zzz-no-match")["items"] == []
    assert srv.search_feedback("user2")["items"][0]["author"] == "user2"  # author searched too


def test_search_feedback_rejects_empty_query_and_bad_limit():
    assert srv.search_feedback("   ")["status"] == "error"
    assert srv.search_feedback("ok", limit=-1)["status"] == "error"


# -- tag_feedback -----------------------------------------------------------------


def test_tag_feedback_happy_path():
    fb_id = ingest_one()
    result = srv.tag_feedback([{"id": fb_id, "urgency": 3, "sentiment": "neg", "theme_id": "th_1"}])
    assert result == {"status": "success", "updated": 1}
    fb = srv.list_feedback()["items"][0]
    assert (fb["urgency"], fb["sentiment"], fb["theme_id"]) == (3, "neg", "th_1")


def test_tag_feedback_partial_update_keeps_other_fields():
    fb_id = ingest_one()
    srv.tag_feedback([{"id": fb_id, "urgency": 2}])
    srv.tag_feedback([{"id": fb_id, "sentiment": "pos"}])
    fb = srv.list_feedback()["items"][0]
    assert (fb["urgency"], fb["sentiment"]) == (2, "pos")


def test_tag_feedback_errors():
    fb_id = ingest_one()
    assert srv.tag_feedback([{"id": "fb_missing000000"}])["status"] == "error"
    assert srv.tag_feedback([{"urgency": 1}])["status"] == "error"  # no id
    assert srv.tag_feedback([{"id": fb_id, "urgency": 9}])["status"] == "error"
    assert srv.tag_feedback([{"id": fb_id, "sentiment": "angry"}])["status"] == "error"


# -- themes -----------------------------------------------------------------------


def test_save_and_list_themes():
    result = srv.save_themes([
        {"title": "Checkout 500s", "summary": "billing broken", "urgency": 3, "trend": "rising"},
        {"title": "CSV export"},
    ])
    assert result["status"] == "success" and result["saved"] == 2
    assert all(re.fullmatch(r"th_[0-9a-f]{12}", i) for i in result["ids"])
    themes = srv.list_themes()["themes"]
    assert len(themes) == 2
    by_title = {t["title"]: t for t in themes}
    assert by_title["Checkout 500s"]["urgency"] == 3
    assert by_title["CSV export"]["trend"] == "new"  # defaults applied
    assert by_title["CSV export"]["feedback_ids"] == []


def test_save_themes_upserts_and_merges_existing():
    th_id = srv.save_themes([{"title": "Slow dashboards", "urgency": 1}])["ids"][0]
    srv.save_themes([{"id": th_id, "urgency": 2}])  # partial update, no title given
    themes = srv.list_themes()["themes"]
    assert len(themes) == 1
    assert themes[0]["title"] == "Slow dashboards" and themes[0]["urgency"] == 2


def test_save_themes_errors():
    assert srv.save_themes([{"summary": "no title"}])["status"] == "error"
    assert srv.save_themes([{"title": "x", "urgency": 7}])["status"] == "error"
    assert srv.save_themes([{"title": "x", "trend": "sideways"}])["status"] == "error"


# -- bets -------------------------------------------------------------------------


def test_save_and_list_bets():
    result = srv.save_bets([{
        "title": "Fix checkout 500",
        "problem": "billing regression",
        "proposal": "rollback + fix",
        "impact": 5, "effort": 2, "confidence": 0.9, "urgency": 3,
        "theme_ids": ["th_1"], "evidence_ids": ["fb_1"],
    }])
    assert result["status"] == "success" and result["saved"] == 1
    bet = srv.list_bets()["bets"][0]
    assert re.fullmatch(r"bet_[0-9a-f]{12}", bet["id"])
    assert bet["status"] == "proposed" and bet["confidence"] == 0.9
    assert bet["created_at"]


def test_save_bets_defaults():
    srv.save_bets([{"title": "Minimal bet"}])
    bet = srv.list_bets()["bets"][0]
    assert (bet["impact"], bet["effort"], bet["confidence"], bet["urgency"]) == (3, 3, 0.5, 0)
    assert bet["theme_ids"] == [] and bet["evidence_ids"] == []


def test_save_bets_errors():
    assert srv.save_bets([{"problem": "no title"}])["status"] == "error"
    assert srv.save_bets([{"title": "x", "impact": 6}])["status"] == "error"
    assert srv.save_bets([{"title": "x", "confidence": 1.5}])["status"] == "error"
    assert srv.save_bets([{"title": "x", "status": "abandoned"}])["status"] == "error"


# -- actions ----------------------------------------------------------------------


def test_record_complete_list_actions():
    rec = srv.record_action({
        "type": "github_issue",
        "target": "lumen/app#12",
        "rationale": "urgent churn risk",
        "evidence_ids": ["fb_1", "fb_2"],
    })
    assert rec["status"] == "success" and re.fullmatch(r"act_[0-9a-f]{12}", rec["id"])
    action = srv.list_actions()["actions"][0]
    assert action["status"] == "proposed" and action["executed_at"] is None

    assert srv.complete_action(rec["id"], "executed", {"issue_url": "https://github.com/x"}) == {
        "status": "success"
    }
    done = srv.list_actions(status="executed")["actions"]
    assert len(done) == 1 and done[0]["executed_at"] is not None
    assert done[0]["result"]["issue_url"] == "https://github.com/x"
    assert srv.list_actions(status="proposed")["actions"] == []


def test_record_action_errors():
    assert srv.record_action({"target": "x"})["status"] == "error"  # missing type
    assert srv.record_action({"type": "tweet"})["status"] == "error"
    assert srv.record_action({"type": "brief", "status": "done"})["status"] == "error"


def test_complete_action_errors():
    assert srv.complete_action("act_missing00000", "executed", {})["status"] == "error"
    act_id = srv.record_action({"type": "brief"})["id"]
    assert srv.complete_action(act_id, "proposed", {})["status"] == "error"


def test_list_actions_rejects_unknown_status():
    assert srv.list_actions(status="pending")["status"] == "error"


# -- briefs -----------------------------------------------------------------------


def test_write_and_get_latest_brief():
    assert srv.get_latest_brief() == {"status": "success", "brief": None}
    first = srv.write_brief("# Week 1", ["th_1"])
    assert first["status"] == "success" and re.fullmatch(r"br_[0-9a-f]{12}", first["id"])
    second = srv.write_brief("# Week 2", [])
    latest = srv.get_latest_brief()["brief"]
    # Same-second timestamps: latest must be one of the two, with full §1 shape.
    assert latest["id"] in {first["id"], second["id"]}
    assert re.fullmatch(r"\d{4}-W\d{2}", latest["week"])
    assert set(latest) == {"id", "week", "markdown", "theme_ids", "created_at"}


def test_write_brief_rejects_empty_markdown():
    assert srv.write_brief("   ", [])["status"] == "error"
    assert srv.write_brief("ok", "th_1")["status"] == "error"  # theme_ids not a list


# -- directives -------------------------------------------------------------------


def test_get_directives_returns_active_only():
    store = srv.get_store()
    store.put("directives", "dir_aaaaaaaaaaaa",
              {"id": "dir_aaaaaaaaaaaa", "text": "escalate churn", "active": True,
               "created_at": "2026-06-01T00:00:00Z"})
    store.put("directives", "dir_bbbbbbbbbbbb",
              {"id": "dir_bbbbbbbbbbbb", "text": "old rule", "active": False,
               "created_at": "2026-06-01T00:00:00Z"})
    directives = srv.get_directives()["directives"]
    assert [d["id"] for d in directives] == ["dir_aaaaaaaaaaaa"]


# -- runs -------------------------------------------------------------------------


def test_start_and_finish_run():
    started = srv.start_run("manual")
    assert started["status"] == "success" and re.fullmatch(r"run_[0-9a-f]{12}", started["id"])
    store = srv.get_store()
    run = store.get("runs", started["id"])
    assert run["status"] == "running" and run["finished_at"] is None
    assert run["counts"] == {"ingested": 0, "themes": 0, "bets": 0, "actions": 0}

    assert srv.finish_run(started["id"], "triaged 88 items", {"ingested": 88, "themes": 6}) == {
        "status": "success"
    }
    run = store.get("runs", started["id"])
    assert run["status"] == "done" and run["finished_at"] is not None
    assert run["summary"] == "triaged 88 items"
    assert run["counts"] == {"ingested": 88, "themes": 6, "bets": 0, "actions": 0}


def test_start_run_rejects_unknown_trigger():
    assert srv.start_run("cron")["status"] == "error"


def test_finish_run_unknown_id():
    assert srv.finish_run("run_missing00000", "x", {})["status"] == "error"
