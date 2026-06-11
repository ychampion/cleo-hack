"""Coder FunctionTools — the coder sub-agent's ONLY hands (CONTRACTS §12).

Plain typed functions (ADK wraps them as FunctionTools), NOT MCP: the sandbox
must live in-process where the model cannot route around it. Every path a tool
touches goes through ``_resolve``, which confines it to ``<repo>/workspace``:

  1. reject absolute/rooted/drive-qualified inputs up front (on Windows,
     ``/etc/passwd`` and ``C:x`` are NOT ``is_absolute()`` yet still escape a
     naive join, hence the ``drive``/``root`` checks);
  2. join against the workspace root, ``Path.resolve()`` (collapses ``..`` and
     follows symlinks), then require ``is_relative_to(workspace_root)``.

Every tool returns a JSON-serializable dict with "status": "success"|"error" —
sandbox violations come back as error dicts, never exceptions, so the model
sees WHY a call was refused and can correct course.
"""

from __future__ import annotations

import difflib
import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = (REPO_ROOT / "workspace").resolve()

# Noise the model never needs to see (or write).
_SKIP_DIRS = {"__pycache__", ".pytest_cache"}

TEST_TIMEOUT_SECONDS = 120
OUTPUT_TAIL_CHARS = 2000


def _resolve(path: str) -> Path:
    """Resolve a workspace-relative path or raise ValueError if it escapes."""
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty string")
    candidate = Path(path.strip())
    # is_absolute() alone is not enough on Windows: "/etc/passwd" (rooted,
    # no drive) and "C:file" (drive, no root) both slip past it but hijack
    # the join below. Reject anything carrying its own anchor.
    if candidate.is_absolute() or candidate.drive or candidate.root:
        raise ValueError(f"absolute paths are not allowed: {path!r}")
    resolved = (WORKSPACE_ROOT / candidate).resolve()
    if not resolved.is_relative_to(WORKSPACE_ROOT):
        raise ValueError(f"path escapes the workspace sandbox: {path!r}")
    return resolved


def list_workspace() -> dict:
    """List every file under workspace/ as workspace-relative POSIX paths.

    Returns:
        {"status": "success", "files": ["lumen_checkout/app.py", ...]}
    """
    if not WORKSPACE_ROOT.is_dir():
        return {"status": "error", "message": "workspace/ directory does not exist"}
    files = sorted(
        p.relative_to(WORKSPACE_ROOT).as_posix()
        for p in WORKSPACE_ROOT.rglob("*")
        if p.is_file()
        and not _SKIP_DIRS.intersection(p.relative_to(WORKSPACE_ROOT).parts)
        and p.suffix != ".pyc"
    )
    return {"status": "success", "files": files}


def read_workspace_file(path: str) -> dict:
    """Read one file from workspace/ (path relative to workspace/, e.g. 'lumen_checkout/app.py').

    Returns:
        {"status": "success", "path": ..., "content": ...} or an error dict.
    """
    try:
        target = _resolve(path)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if not target.is_file():
        return {"status": "error", "message": f"no such workspace file: {path!r}"}
    try:
        content = target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"status": "error", "message": f"could not read {path!r}: {exc}"}
    return {"status": "success", "path": path, "content": content}


def write_workspace_file(path: str, content: str) -> dict:
    """Write (create or overwrite) one file under workspace/ with the full new content.

    Returns line-diff counts against the previous content:
        {"status": "success", "path": ..., "created": bool,
         "lines_added": int, "lines_removed": int}
    """
    try:
        target = _resolve(path)
    except ValueError as exc:
        return {"status": "error", "message": str(exc)}
    if not isinstance(content, str):
        return {"status": "error", "message": "content must be a string"}
    created = not target.exists()
    old = "" if created else target.read_text(encoding="utf-8")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return {"status": "error", "message": f"could not write {path!r}: {exc}"}
    diff = difflib.unified_diff(old.splitlines(), content.splitlines(), lineterm="")
    added = removed = 0
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1
    return {
        "status": "success",
        "path": path,
        "created": created,
        "lines_added": added,
        "lines_removed": removed,
    }


def run_workspace_tests() -> dict:
    """Run the workspace acceptance suite (pytest on workspace/lumen_checkout/tests).

    Returns:
        {"status": "success", "passed": int, "failed": int, "output_tail": str}
        status is "error" only when pytest could not run/collect (timeout,
        crash, bad collection) — failing tests are a SUCCESSFUL measurement.
    """
    # The subprocess only needs to run offline tests; never hand it the
    # GOOGLE_API_KEY (no accidental model calls billed from inside a tool).
    env = {k: v for k, v in os.environ.items() if k != "GOOGLE_API_KEY"}
    cmd = [sys.executable, "-m", "pytest", "workspace/lumen_checkout/tests", "-q"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "message": f"pytest timed out after {TEST_TIMEOUT_SECONDS}s",
            "passed": 0,
            "failed": 0,
            "output_tail": "",
        }
    output = (proc.stdout or "") + (proc.stderr or "")
    tail = output[-OUTPUT_TAIL_CHARS:]
    passed_m = re.search(r"(\d+) passed", output)
    failed_m = re.search(r"(\d+) failed", output)
    passed = int(passed_m.group(1)) if passed_m else 0
    failed = int(failed_m.group(1)) if failed_m else 0
    # pytest exit codes: 0 all passed, 1 some failed — both are valid
    # measurements; anything else means the suite itself could not run.
    if proc.returncode not in (0, 1):
        return {
            "status": "error",
            "message": f"pytest exited with code {proc.returncode}",
            "passed": passed,
            "failed": failed,
            "output_tail": tail,
        }
    return {"status": "success", "passed": passed, "failed": failed, "output_tail": tail}
