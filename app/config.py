"""Cleo workspace configuration — tiny, dependency-free (stdlib only).

This is how you point Cleo at YOUR company instead of the demo corpus: one
optional ``cleo.config.json`` at the repo root (copy ``cleo.config.example.json``)
plus the same environment variables that always worked.

Precedence (highest wins), per key:

1. **Environment variables** — ``CLEO_WORKSPACE_NAME``, ``GITHUB_DEMO_REPO``,
   ``CORPUS_DIR`` (a single directory, kept for backward compatibility),
   ``CLEO_MODEL``. A *blank* value counts as unset — ``.env`` templates ship
   empty lines like ``GITHUB_DEMO_REPO=`` and those must not mask the file.
2. **``cleo.config.json``** — located via ``CLEO_CONFIG_PATH`` (relative paths
   resolve against the repo root), default ``<repo root>/cleo.config.json``.
   JSON has no comments, so keys starting with ``_`` are treated as comments
   and ignored. Unknown keys are ignored. A missing file is normal (the file
   is optional); an unreadable/invalid file warns and is skipped — the loader
   never crashes.
3. **Built-in defaults** — see ``DEFAULTS``.

Keys:

- ``workspace_name`` (str)  — display name for your team/workspace.
- ``github_repo``    (str)  — ``owner/repo`` Cleo ingests issues from and
  escalates to. The token (``GITHUB_TOKEN``) is a secret and stays env-only.
- ``corpus_dirs``    (list[str]) — directories of YOUR documents (call
  transcripts, meeting notes, support exports as ``.md`` drop-ins). The env
  override ``CORPUS_DIR`` is a single dir and becomes a one-item list.
- ``model``          (str)  — Gemini model id.

Env bridge (WHY): a few modules outside this loader still read the
environment directly and are owned by other components — ``action_guard``
(``agents/cleo/callbacks.py``) validates GitHub write targets against
``GITHUB_DEMO_REPO``, the actor embeds it in its instruction, and
``agents/cleo/model.py`` reads ``CLEO_MODEL``. So when a value comes from the
config *file* and the corresponding env var is blank, the loader exports the
resolved value into ``os.environ`` — making the whole system agree on one
repo/model without touching those modules. Env always wins: a non-blank env
var is never overwritten, and nothing is exported for plain defaults.

The merged config is cached after the first ``get_config()``; call
``reset_config()`` (tests do) to re-read env + file.
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path
from typing import Any

# This file lives at app/config.py — repo root is one level up. Derived from
# __file__, never from the process cwd, so adk web / uvicorn / pytest agree.
REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_CONFIG_FILENAME = "cleo.config.json"

DEFAULTS: dict[str, Any] = {
    "workspace_name": "My Company",
    "github_repo": "",
    "corpus_dirs": ["seed/corpus"],
    "model": "gemini-3.5-flash",
}

# config key -> overriding environment variable.
_ENV_VARS = {
    "workspace_name": "CLEO_WORKSPACE_NAME",
    "github_repo": "GITHUB_DEMO_REPO",
    "corpus_dirs": "CORPUS_DIR",
    "model": "CLEO_MODEL",
}

# File-sourced values exported back into the environment for the env-reading
# consumers listed in the module docstring. CORPUS_DIR is deliberately NOT
# bridged: it is single-dir (would drop extra corpus_dirs) and seed/seed.py
# uses it to locate the *demo* corpus layout.
_ENV_BRIDGE_KEYS = ("github_repo", "model")

_cache: dict[str, Any] | None = None


def config_path() -> Path:
    """Absolute path of the workspace config file (may not exist)."""
    raw = os.environ.get("CLEO_CONFIG_PATH", "").strip()
    path = Path(raw) if raw else Path(DEFAULT_CONFIG_FILENAME)
    return path if path.is_absolute() else REPO_ROOT / path


def _warn(message: str) -> None:
    warnings.warn(f"[cleo.config] {message}", RuntimeWarning, stacklevel=4)


def _coerce(key: str, value: Any, source: str) -> Any | None:
    """Validate one file-layer value; return None (and warn) when unusable."""
    if key == "corpus_dirs":
        if isinstance(value, str):  # single dir as a bare string: be forgiving
            value = [value]
        if (
            isinstance(value, list)
            and value
            and all(isinstance(v, str) and v.strip() for v in value)
        ):
            return [v.strip() for v in value]
        _warn(f"ignoring 'corpus_dirs' in {source}: expected a non-empty list of strings")
        return None
    if isinstance(value, str):
        return value.strip()
    _warn(f"ignoring '{key}' in {source}: expected a string, got {type(value).__name__}")
    return None


def _file_layer() -> dict[str, Any]:
    """Values from cleo.config.json — {} on any problem, never an exception."""
    path = config_path()
    if not path.is_file():
        if os.environ.get("CLEO_CONFIG_PATH", "").strip():
            # Only warn when the user explicitly pointed at a file; the
            # default path being absent is the normal no-config case.
            _warn(f"CLEO_CONFIG_PATH points at missing file {path}; using env/defaults")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _warn(f"could not read {path} ({exc}); using env/defaults")
        return {}
    if not isinstance(data, dict):
        _warn(f"{path} must contain a JSON object; using env/defaults")
        return {}

    layer: dict[str, Any] = {}
    for key, value in data.items():
        if key.startswith("_"):
            continue  # comment convention — JSON has no native comments
        if key not in DEFAULTS:
            continue  # unknown keys ignored: forward/backward compatible
        coerced = _coerce(key, value, source=str(path))
        if coerced is not None:
            layer[key] = coerced
    return layer


def _env_layer() -> dict[str, Any]:
    """Values from the environment; blank values count as unset."""
    layer: dict[str, Any] = {}
    for key, var in _ENV_VARS.items():
        raw = os.environ.get(var, "").strip()
        if not raw:
            continue
        layer[key] = [raw] if key == "corpus_dirs" else raw
    return layer


def _export_env_bridge(file_layer: dict[str, Any]) -> None:
    """Export file-sourced repo/model to env for env-reading consumers."""
    for key in _ENV_BRIDGE_KEYS:
        if key not in file_layer:
            continue
        var = _ENV_VARS[key]
        if not os.environ.get(var, "").strip():
            os.environ[var] = file_layer[key]


def get_config() -> dict[str, Any]:
    """Merged workspace config (env > cleo.config.json > defaults), cached."""
    global _cache
    if _cache is None:
        file_layer = _file_layer()
        _export_env_bridge(file_layer)
        _cache = {**DEFAULTS, **file_layer, **_env_layer()}
    # Shallow-copy (and re-list corpus_dirs) so callers can't mutate the cache.
    return {**_cache, "corpus_dirs": list(_cache["corpus_dirs"])}


def reset_config() -> None:
    """Drop the cache so the next get_config() re-reads env + file (tests)."""
    global _cache
    _cache = None
