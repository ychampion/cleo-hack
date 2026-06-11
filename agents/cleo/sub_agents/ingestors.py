"""Ingest stage: one LlmAgent per feedback source, fanned out in parallel.

WHY ``ParallelAgent``: the sources are independent I/O-bound pulls (GitHub
issues over Streamable-HTTP MCP, corpus files over stdio filesystem MCP), so
running them as parallel branches halves wall-clock ingest time and
demonstrates real concurrent MCP sessions. Each branch normalizes its source
into the CONTRACTS §1 feedback shape and writes through the store's
``ingest_feedback`` tool, which dedupes on (source, external_id) — re-running
the stage is idempotent by construction, which is what lets ``watch_loop``
iterate safely.

Composition is environment-aware at import time: the GitHub branch only joins
the stage when both ``GITHUB_TOKEN`` and a target repo are configured (no
token -> no toolset; no repo -> nothing deterministic to list).

Workspace wiring: the GitHub repo and the corpus roots resolve through
``app.config.get_config()`` (env > ``cleo.config.json`` > defaults), so a
company points Cleo at its own repo and its own document folders without
touching this module — and multiple ``corpus_dirs`` fan into ONE docs
ingestor whose filesystem toolset allows every root.
"""

from __future__ import annotations

from google.adk.agents import LlmAgent, ParallelAgent

from ..model import cleo_model
from ..toolsets import corpus_dirs, github_repo, make_github_toolset, make_store_toolset


def _model():
    return cleo_model()


def make_github_ingestor(suffix: str = "") -> LlmAgent | None:
    """GitHub issues -> feedback rows. None when GitHub isn't configured."""
    # Repo via app.config (env GITHUB_DEMO_REPO > cleo.config.json > "");
    # the token stays env-only inside make_github_toolset.
    toolset = make_github_toolset(read_only=True)
    repo = github_repo().strip()
    if toolset is None or "/" not in repo:
        return None
    owner, repo_name = repo.split("/", 1)
    return LlmAgent(
        name=f"github_ingestor{suffix}",
        model=_model(),
        description="Pulls open GitHub issues and ingests them as feedback.",
        instruction=f"""You ingest GitHub issues as product feedback. Work silently and efficiently.

Step 1 — call `list_issues` with owner="{owner}", repo="{repo_name}", state="open", perPage=30.

Step 2 — map EVERY returned issue (skip pull requests) to a feedback item:
{{"source": "github", "external_id": "<issue number as string>", "author": "<user login>",
 "text": "<title>\\n\\n<body, may be empty>", "url": "<html_url>", "created_at": "<issue created_at>",
 "metadata": {{"labels": ["..."], "state": "open"}}}}
Do NOT set id, urgency, sentiment or theme_id — the store assigns ids and the
synthesizer does the triage tagging.

Step 3 — call `ingest_feedback` ONCE with the full items list. It dedupes on
(source, external_id), so already-seen issues are reported as duplicates — that is fine.

Step 4 — reply with exactly one line: `github: ingested <N> (<D> duplicates)`.
If `list_issues` errors, reply `github: failed — <one-line reason>` instead. Never retry more than once.""",
        tools=[toolset, make_store_toolset(["ingest_feedback"])],
        output_key=f"ingest_github{suffix}",
    )


def make_docs_ingestor(suffix: str = "") -> LlmAgent:
    """Call transcripts + docs from the configured corpus roots -> feedback rows.

    Supports MULTIPLE corpus roots (``corpus_dirs`` in cleo.config.json): the
    filesystem MCP server is launched with every root as an allowed directory,
    and the instruction enumerates each root explicitly so the model never has
    to guess which paths it may list.
    """
    from ..toolsets import make_filesystem_toolset  # local: may probe PATH for npx

    fs_toolset = make_filesystem_toolset()
    roots = [root.as_posix() for root in corpus_dirs()]
    roots_block = "\n".join(f"- {root}" for root in roots)
    tools = [make_store_toolset(["ingest_feedback"])]
    if fs_toolset is not None:
        tools.insert(0, fs_toolset)

    if fs_toolset is None:
        # No node/npx on this machine: the agent must not pretend it read files.
        instruction = (
            "Your filesystem tools are unavailable in this environment, so you "
            "cannot read the corpus. Reply with exactly: "
            "`docs: skipped (filesystem connector unavailable)`. Do not call any tool."
        )
    else:
        instruction = f"""You ingest customer call transcripts and notes documents as product feedback.

Your corpus roots (the only directories you may read):
{roots_block}

Step 1 — for EACH corpus root above, call `list_directory` on the root itself,
then on every subdirectory it reports (e.g. call-transcripts/, docs/).

Step 2 — `read_file` every .md file found (skip anything else).

Step 3 — extract feedback items. One item = one distinct customer statement
(complaint, request, praise, churn signal). For call transcripts (files under a
call-transcripts/ directory, or clearly a conversation) use source "call"; for
every other document use source "doc". Shape each item as:
{{"source": "call", "external_id": "<filename>#<n>", "author": "<speaker or doc title>",
 "text": "<verbatim or tightly paraphrased statement>", "url": null,
 "created_at": "<date mentioned in the file, else today ISO-8601 UTC>",
 "metadata": {{"file": "<filename>"}}}}
Number <n> sequentially from 1 within each file so external_ids are stable across
runs (the store dedupes on source+external_id). Do NOT set id/urgency/sentiment/theme_id.

Step 4 — call `ingest_feedback` ONCE with all items from all files.

Step 5 — reply with exactly one line: `docs: ingested <N> (<D> duplicates)`.
If a directory is missing or empty, just report what you did ingest; if nothing,
reply `docs: ingested 0 (0 duplicates)`."""

    return LlmAgent(
        name=f"docs_ingestor{suffix}",
        model=_model(),
        description="Reads corpus call transcripts/docs via filesystem MCP and ingests feedback.",
        instruction=instruction,
        tools=tools,
        output_key=f"ingest_docs{suffix}",
    )


def make_ingest_stage(suffix: str = "") -> ParallelAgent:
    """Fan-out stage: all configured source ingestors run concurrently."""
    branches = [make_docs_ingestor(suffix)]
    github = make_github_ingestor(suffix)
    if github is not None:
        branches.insert(0, github)
    return ParallelAgent(
        name=f"ingest_stage{suffix}",
        description="Pulls feedback from all configured sources in parallel.",
        sub_agents=branches,
    )
