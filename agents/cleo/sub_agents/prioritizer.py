"""Prioritizer: synthesis -> structured, evidence-backed bet proposals.

WHY tool-free + ``output_schema``: ADK forbids tools on an LlmAgent with an
``output_schema`` (constrained decoding and function-calling are mutually
exclusive), so this stage deliberately has NO tools. Everything it needs
arrives via the ``{synthesis}`` state placeholder written by the synthesizer's
``output_key``, and its validated JSON lands in state under ``bets`` for the
actor to persist. ``include_contents="none"`` keeps the model's context to
exactly the instruction + synthesis — no conversation noise, deterministic
behavior, cheaper calls.
"""

from __future__ import annotations

import os

from google.adk.agents import LlmAgent
from ..model import cleo_model

from ..schemas import BetProposals


def make_prioritizer(suffix: str = "") -> LlmAgent:
    return LlmAgent(
        name=f"prioritizer{suffix}",
        model=cleo_model(),
        description=(
            "Turns the synthesis report into 3-5 structured product bets "
            "(strict JSON via output_schema)."
        ),
        instruction="""You are Cleo's prioritizer. From the synthesis report below, propose the product
bets the team should make next. Output ONLY the JSON object matching the schema.

Synthesis report:
{synthesis}

Rules:
- Propose 3 to 5 bets, ordered most urgent first.
- Each bet must cite theme_ids (th_...) and evidence_ids (fb_...) copied
  VERBATIM from the synthesis report. A bet with no evidence_ids is invalid.
- urgency mirrors the driving theme's urgency (0-3). Any theme listed under
  "Urgent" must produce a bet with urgency >= 2.
- impact and effort are integers 1-5; confidence is 0.0-1.0 and should reflect
  how many independent feedback items support the bet.
- problem states the user pain in one or two sentences grounded in the quotes;
  proposal is the concrete change to ship, not a vague goal.
- If the synthesis reports a contradiction, either resolve it inside one bet's
  proposal (state the chosen default and why) or lower that bet's confidence.""",
        tools=[],  # REQUIRED empty: output_schema and tools are mutually exclusive
        output_schema=BetProposals,
        output_key="bets",
        include_contents="none",
    )
