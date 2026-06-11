"""app/config.py tests: precedence, multi-corpus, "_"-keys, cache, bad files.

Offline and deterministic (CONTRACTS §9): pure stdlib loader, tmp files only.
Every test pins CLEO_CONFIG_PATH to a tmp file so a developer's real
cleo.config.json (optional, not shipped — only the .example is) can never leak in.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config as cfg  # noqa: E402

ALL_ENV_VARS = (
    "CLEO_WORKSPACE_NAME",
    "GITHUB_DEMO_REPO",
    "CORPUS_DIR",
    "CLEO_MODEL",
    "CLEO_CONFIG_PATH",
)


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    """Blank env slate + a tmp (empty-object) config file, cache reset around each test."""
    for var in ALL_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    path = tmp_path / "cleo.config.json"
    path.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CLEO_CONFIG_PATH", str(path))
    cfg.reset_config()
    yield path
    cfg.reset_config()


def write_config(path: Path, data) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")
    cfg.reset_config()


# -- defaults -------------------------------------------------------------------------


def test_defaults_when_no_env_and_empty_file(isolated_config):
    config = cfg.get_config()
    assert config["workspace_name"] == "My Company"
    assert config["github_repo"] == ""
    assert config["corpus_dirs"] == ["seed/corpus"]
    assert config["model"] == "gemini-3.5-flash"


# -- precedence: env > file > default -------------------------------------------------


def test_file_beats_defaults(isolated_config):
    write_config(
        isolated_config,
        {
            "workspace_name": "Acme",
            "github_repo": "acme/product",
            "corpus_dirs": ["notes", "exports"],
            "model": "gemini-3.5-pro",
        },
    )
    config = cfg.get_config()
    assert config["workspace_name"] == "Acme"
    assert config["github_repo"] == "acme/product"
    assert config["corpus_dirs"] == ["notes", "exports"]
    assert config["model"] == "gemini-3.5-pro"


def test_env_beats_file(isolated_config, monkeypatch):
    write_config(
        isolated_config,
        {
            "workspace_name": "FileCo",
            "github_repo": "file/repo",
            "corpus_dirs": ["file-dir-a", "file-dir-b"],
            "model": "file-model",
        },
    )
    monkeypatch.setenv("CLEO_WORKSPACE_NAME", "EnvCo")
    monkeypatch.setenv("GITHUB_DEMO_REPO", "env/repo")
    monkeypatch.setenv("CORPUS_DIR", "env-dir")
    monkeypatch.setenv("CLEO_MODEL", "env-model")
    cfg.reset_config()
    config = cfg.get_config()
    assert config["workspace_name"] == "EnvCo"
    assert config["github_repo"] == "env/repo"
    assert config["corpus_dirs"] == ["env-dir"]  # CORPUS_DIR -> single-item list
    assert config["model"] == "env-model"


def test_blank_env_falls_through_to_file(isolated_config, monkeypatch):
    """.env templates ship blank lines (GITHUB_DEMO_REPO=) — blank must not mask the file."""
    write_config(isolated_config, {"github_repo": "file/repo"})
    monkeypatch.setenv("GITHUB_DEMO_REPO", "")
    monkeypatch.setenv("CLEO_MODEL", "   ")
    cfg.reset_config()
    config = cfg.get_config()
    assert config["github_repo"] == "file/repo"
    assert config["model"] == "gemini-3.5-flash"


# -- corpus_dirs parsing ---------------------------------------------------------------


def test_multi_corpus_dirs_preserved_in_order(isolated_config):
    dirs = ["seed/corpus", "docs/customer-notes", "C:/exports/intercom"]
    write_config(isolated_config, {"corpus_dirs": dirs})
    assert cfg.get_config()["corpus_dirs"] == dirs


def test_corpus_dirs_bare_string_coerced_to_list(isolated_config):
    write_config(isolated_config, {"corpus_dirs": "my-notes"})
    assert cfg.get_config()["corpus_dirs"] == ["my-notes"]


def test_corpus_dirs_invalid_type_warns_and_keeps_default(isolated_config):
    write_config(isolated_config, {"corpus_dirs": 42})
    with pytest.warns(RuntimeWarning, match="corpus_dirs"):
        config = cfg.get_config()
    assert config["corpus_dirs"] == ["seed/corpus"]


# -- "_"-prefixed comment keys + unknown keys ------------------------------------------


def test_underscore_and_unknown_keys_ignored(isolated_config):
    write_config(
        isolated_config,
        {
            "_readme": ["this is a comment"],
            "_github_repo": "comment about the key below",
            "github_repo": "acme/product",
            "totally_unknown_key": "ignored",
        },
    )
    config = cfg.get_config()
    assert config["github_repo"] == "acme/product"
    assert "_readme" not in config
    assert "_github_repo" not in config
    assert "totally_unknown_key" not in config
    assert set(config) == set(cfg.DEFAULTS)


# -- cache + reset ----------------------------------------------------------------------


def test_cache_holds_until_reset(isolated_config, monkeypatch):
    assert cfg.get_config()["model"] == "gemini-3.5-flash"
    monkeypatch.setenv("CLEO_MODEL", "changed-model")
    assert cfg.get_config()["model"] == "gemini-3.5-flash"  # cached
    cfg.reset_config()
    assert cfg.get_config()["model"] == "changed-model"  # re-read after reset


def test_returned_dict_mutation_does_not_poison_cache(isolated_config):
    config = cfg.get_config()
    config["model"] = "mutated"
    config["corpus_dirs"].append("mutated-dir")
    fresh = cfg.get_config()
    assert fresh["model"] == "gemini-3.5-flash"
    assert fresh["corpus_dirs"] == ["seed/corpus"]


# -- missing / invalid file tolerance ---------------------------------------------------


def test_missing_explicit_file_warns_and_uses_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("CLEO_CONFIG_PATH", str(tmp_path / "does-not-exist.json"))
    cfg.reset_config()
    with pytest.warns(RuntimeWarning, match="missing file"):
        config = cfg.get_config()
    assert config == cfg.get_config()  # second call served from cache, no crash
    assert config["workspace_name"] == "My Company"
    assert config["corpus_dirs"] == ["seed/corpus"]


def test_invalid_json_warns_and_uses_defaults(isolated_config):
    isolated_config.write_text("not json {{{", encoding="utf-8")
    cfg.reset_config()
    with pytest.warns(RuntimeWarning, match="could not read"):
        config = cfg.get_config()
    assert config["model"] == "gemini-3.5-flash"
    assert config["corpus_dirs"] == ["seed/corpus"]


def test_non_object_json_warns_and_uses_defaults(isolated_config):
    write_config(isolated_config, [1, 2, 3])
    with pytest.warns(RuntimeWarning, match="JSON object"):
        config = cfg.get_config()
    assert config["workspace_name"] == "My Company"


def test_wrong_typed_scalar_warns_and_keeps_default(isolated_config):
    write_config(isolated_config, {"model": 5, "workspace_name": "Acme"})
    with pytest.warns(RuntimeWarning, match="'model'"):
        config = cfg.get_config()
    assert config["model"] == "gemini-3.5-flash"  # bad key dropped…
    assert config["workspace_name"] == "Acme"  # …good keys still applied


def test_env_beats_invalid_file(isolated_config, monkeypatch):
    """A broken file must never block env config — the agent still boots."""
    isolated_config.write_text("not json {{{", encoding="utf-8")
    monkeypatch.setenv("GITHUB_DEMO_REPO", "env/repo")
    cfg.reset_config()
    with pytest.warns(RuntimeWarning):
        config = cfg.get_config()
    assert config["github_repo"] == "env/repo"


# -- env bridge (file-sourced repo/model exported for env-reading modules) --------------


def test_file_repo_and_model_exported_to_env_when_blank(isolated_config, monkeypatch):
    write_config(isolated_config, {"github_repo": "acme/product", "model": "file-model"})
    monkeypatch.setenv("GITHUB_DEMO_REPO", "")  # blank == unset (typical .env line)
    cfg.reset_config()
    cfg.get_config()
    # action_guard / actor / model.py read these env vars directly.
    assert os.environ["GITHUB_DEMO_REPO"] == "acme/product"
    assert os.environ["CLEO_MODEL"] == "file-model"


def test_env_bridge_never_overwrites_real_env(isolated_config, monkeypatch):
    write_config(isolated_config, {"github_repo": "file/repo", "model": "file-model"})
    monkeypatch.setenv("GITHUB_DEMO_REPO", "env/repo")
    monkeypatch.setenv("CLEO_MODEL", "env-model")
    cfg.reset_config()
    config = cfg.get_config()
    assert os.environ["GITHUB_DEMO_REPO"] == "env/repo"
    assert os.environ["CLEO_MODEL"] == "env-model"
    assert config["github_repo"] == "env/repo"
    assert config["model"] == "env-model"


def test_no_bridge_export_for_plain_defaults(isolated_config):
    cfg.get_config()  # nothing in the file layer -> nothing exported
    assert "GITHUB_DEMO_REPO" not in os.environ
    assert "CLEO_MODEL" not in os.environ
