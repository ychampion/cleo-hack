"""Store tests: CRUD, payload filters, env-based construction (CONTRACTS §0/§9)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.store import Store, new_id, utc_now  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


def test_put_get_roundtrip(store):
    doc = {"id": "fb_000000000001", "source": "slack", "text": "hello", "metadata": {"a": 1}}
    store.put("feedback", doc["id"], doc)
    assert store.get("feedback", doc["id"]) == doc


def test_get_missing_returns_none(store):
    assert store.get("feedback", "fb_nope") is None


def test_put_upserts_without_duplicating(store):
    store.put("themes", "th_1", {"id": "th_1", "title": "old"})
    store.put("themes", "th_1", {"id": "th_1", "title": "new"})
    assert store.count("themes") == 1
    assert store.get("themes", "th_1")["title"] == "new"


def test_delete(store):
    store.put("bets", "bet_1", {"id": "bet_1", "title": "x"})
    assert store.delete("bets", "bet_1") is True
    assert store.get("bets", "bet_1") is None
    assert store.delete("bets", "bet_1") is False


def test_collections_are_isolated(store):
    store.put("feedback", "x", {"id": "x", "kind": "fb"})
    store.put("themes", "x", {"id": "x", "kind": "th"})
    assert store.get("feedback", "x")["kind"] == "fb"
    assert store.get("themes", "x")["kind"] == "th"
    assert store.count("feedback") == 1


def test_list_equality_filters_on_payload_fields(store):
    store.put("feedback", "a", {"id": "a", "source": "slack", "urgency": 3})
    store.put("feedback", "b", {"id": "b", "source": "slack", "urgency": 1})
    store.put("feedback", "c", {"id": "c", "source": "intercom", "urgency": 3})
    assert {d["id"] for d in store.list("feedback", source="slack")} == {"a", "b"}
    assert [d["id"] for d in store.list("feedback", source="slack", urgency=3)] == ["a"]
    assert store.list("feedback", source="github") == []


def test_list_none_filter_matches_json_null_and_missing(store):
    store.put("feedback", "a", {"id": "a", "theme_id": None})
    store.put("feedback", "b", {"id": "b", "theme_id": "th_1"})
    store.put("feedback", "c", {"id": "c"})  # key missing entirely
    assert {d["id"] for d in store.list("feedback", theme_id=None)} == {"a", "c"}


def test_list_bool_filter(store):
    store.put("directives", "d1", {"id": "d1", "active": True})
    store.put("directives", "d2", {"id": "d2", "active": False})
    assert [d["id"] for d in store.list("directives", active=True)] == ["d1"]


def test_list_limit(store):
    for i in range(5):
        store.put("feedback", f"fb_{i}", {"id": f"fb_{i}"})
    assert len(store.list("feedback", limit=3)) == 3


def test_list_rejects_invalid_filter_field(store):
    with pytest.raises(ValueError):
        store.list("feedback", **{"bad field": 1})


def test_search_text_case_insensitive(store):
    store.put("feedback", "a", {"id": "a", "text": "Checkout returns a 500", "author": "Dan"})
    store.put("feedback", "b", {"id": "b", "text": "love the digest", "author": "Owen"})
    assert [d["id"] for d in store.search_text("feedback", "CHECKOUT")] == ["a"]
    assert [d["id"] for d in store.search_text("feedback", "owen", fields=("text", "author"))] == ["b"]
    assert store.search_text("feedback", "nomatch") == []


def test_env_path_used_at_construction(tmp_path, monkeypatch):
    db = tmp_path / "env.db"
    monkeypatch.setenv("CLEO_DB_PATH", str(db))
    s = Store()
    try:
        s.put("runs", "run_1", {"id": "run_1"})
        assert db.exists()
        assert s.db_path == db
    finally:
        s.close()


def test_explicit_path_overrides_env(tmp_path, monkeypatch):
    monkeypatch.setenv("CLEO_DB_PATH", str(tmp_path / "env.db"))
    explicit = tmp_path / "explicit.db"
    s = Store(explicit)
    try:
        assert s.db_path == explicit
    finally:
        s.close()


def test_wal_mode_enabled(store):
    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_new_id_scheme():
    for prefix in ("fb", "th", "bet", "act", "br", "dir", "run"):
        assert re.fullmatch(rf"{prefix}_[0-9a-f]{{12}}", new_id(prefix))
    assert new_id("fb") != new_id("fb")


def test_utc_now_iso_format():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", utc_now())
