"""Cleo ADK app package.

ADK's agent loader imports ``agents.cleo.agent`` and reads ``root_agent`` from
it; re-exporting here keeps the package importable both ways
(``from agents.cleo import agent`` and ``from agents.cleo.agent import root_agent``).
"""

from . import agent  # noqa: F401
