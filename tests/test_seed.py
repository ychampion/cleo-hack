"""Seed tests: idempotency, corpus integrity, engineered narrative counts (CONTRACTS §7/§9)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server import server as srv  # noqa: E402
from seed import seed  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "seed" / "corpus"

# Verified corpus composition (see seed/corpus/*): ~90 items per CONTRACTS §7.
EXPECTED = {"slack": 30, "intercom": 25, "call": 22, "doc": 11}
EXPECTED_TOTAL = sum(EXPECTED.values())  # 88


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("CLEO_DB_PATH", str(tmp_path / "cleo.db"))
    monkeypatch.delenv("GITHUB_DEMO_REPO", raising=False)
    monkeypatch.delenv("CORPUS_DIR", raising=False)
    yield


# -- corpus integrity ---------------------------------------------------------------


def test_corpus_files_exist_and_parse():
    assert json.loads((CORPUS / "slack-export.json").read_text(encoding="utf-8"))["messages"]
    assert json.loads((CORPUS / "tickets.json").read_text(encoding="utf-8"))
    assert len(list((CORPUS / "call-transcripts").glob("*.md"))) == 3
    assert len(list((CORPUS / "docs").glob("*.md"))) == 2


def test_build_items_counts_and_shape():
    items = seed.build_items()
    assert len(items) == EXPECTED_TOTAL
    by_source: dict[str, int] = {}
    for item in items:
        by_source[item["source"]] = by_source.get(item["source"], 0) + 1
        assert item["text"].strip()
        assert item["author"] and item["author"] != "unknown"
        assert item["external_id"]
    assert by_source == EXPECTED
    # Unique (source, external_id) keys — nothing silently collides.
    keys = [(i["source"], i["external_id"]) for i in items]
    assert len(set(keys)) == len(keys)


def test_timestamps_spread_over_three_weeks_ending_2026_06_10():
    dates = sorted(i["created_at"] for i in seed.build_items())
    assert dates[0].startswith("2026-05-20")
    assert dates[-1].startswith("2026-06-10")


def test_narrative_covers_six_themes_and_contradiction():
    items = seed.build_items()
    text = " ".join(i["text"].lower() for i in items)

    def mentions(*words: str) -> int:
        return sum(1 for i in items if all(w in i["text"].lower() for w in words))

    # Two urgent storylines, well represented across the corpus.
    assert mentions("checkout") >= 10 and "500" in text
    assert mentions("okta") + mentions("sso") >= 8
    # Churn threats attached to the checkout storyline.
    assert any(
        "checkout" in i["text"].lower() or "upgrade" in i["text"].lower()
        for i in items
        if "alternative" in i["text"].lower() or "refund" in i["text"].lower()
    )
    # Remaining themes.
    assert mentions("csv") >= 6
    assert mentions("slow") + mentions("seconds") >= 6
    assert mentions("invite") + mentions("onboarding") + mentions("backfill") >= 6
    assert mentions("webhook") >= 5
    # Genuine contradiction: digests default ON vs default OFF.
    assert mentions("digest", "default") >= 2
    assert any("on by default" in i["text"].lower() for i in items)
    assert any("opt-in" in i["text"].lower() for i in items)


# -- seeding ------------------------------------------------------------------------


def test_seed_populates_store():
    summary = seed.main()
    assert summary["ingested"] == EXPECTED_TOTAL
    assert summary["duplicates"] == 0
    assert summary["feedback_total"] == EXPECTED_TOTAL
    assert summary["directives"] == 2
    # All ingested as untriaged, ready for the agent.
    untriaged = srv.list_feedback(only_untriaged=True, limit=200)["items"]
    assert len(untriaged) == EXPECTED_TOTAL
    for source, count in EXPECTED.items():
        assert len(srv.list_feedback(source=source, limit=200)["items"]) == count


def test_seed_is_idempotent():
    first = seed.main()
    second = seed.main()
    assert second["ingested"] == 0
    assert second["duplicates"] == first["ingested"] == EXPECTED_TOTAL
    assert second["feedback_total"] == EXPECTED_TOTAL
    assert len(srv.get_directives()["directives"]) == 2


def test_directives_use_github_demo_repo_env_with_fallback(monkeypatch):
    seed.main()
    texts = [d["text"] for d in srv.get_directives()["directives"]]
    assert any("the demo repo" in t for t in texts)
    assert any("brief" in t.lower() for t in texts)

    # Re-seeding with the env set updates the directive in place (no duplicate).
    monkeypatch.setenv("GITHUB_DEMO_REPO", "lumen-hq/lumen-app")
    seed.main()
    directives = srv.get_directives()["directives"]
    assert len(directives) == 2
    assert any("lumen-hq/lumen-app" in d["text"] for d in directives)
    assert not any("the demo repo" in d["text"] for d in directives)


def test_directive_ids_follow_scheme():
    seed.main()
    import re

    for directive in srv.get_directives()["directives"]:
        assert re.fullmatch(r"dir_[0-9a-f]{12}", directive["id"])
        assert directive["active"] is True
        assert directive["created_at"]
