"""Cleo's triage-stage sub-agents.

Every stage is built by a factory taking a ``suffix`` so the same pipeline can
exist twice in one agent tree (standalone ``triage_pipeline`` and inside
``watch_loop``) — ADK requires globally unique agent names and a single parent
per agent instance.
"""

from .actor import make_actor
from .ingestors import make_ingest_stage
from .prioritizer import make_prioritizer
from .synthesizer import make_synthesizer

__all__ = [
    "make_actor",
    "make_ingest_stage",
    "make_prioritizer",
    "make_synthesizer",
]
