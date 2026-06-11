"""Pydantic schemas for structured agent output (CONTRACTS §1 "bets").

WHY ``output_schema``: the prioritizer is the one stage whose output must be
machine-consumable (the actor saves it verbatim via ``save_bets`` and the UI
renders it). ADK's ``output_schema`` forces gemini into constrained JSON
decoding, which is far more reliable than prompt-and-parse.

WHY ``id``/``status``/``created_at`` are NOT in the LLM schema: those fields
are stamped by the feedback store at save time (``save_bets`` assigns
``bet_<12hex>`` ids, status defaults to "proposed"). Letting the model emit
them invites hallucinated ids that would corrupt the evidence graph, so the
schema is restricted to the fields only the model can know.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BetProposal(BaseModel):
    """One evidence-backed product bet (CONTRACTS §1 ``bets`` payload)."""

    title: str = Field(description="Short imperative title for the bet.")
    problem: str = Field(
        description="The user problem, grounded in the feedback evidence."
    )
    proposal: str = Field(description="Concrete product change to make.")
    impact: int = Field(ge=1, le=5, description="Expected impact, 1-5.")
    effort: int = Field(ge=1, le=5, description="Estimated effort, 1-5.")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence the evidence supports the bet, 0-1."
    )
    urgency: int = Field(
        ge=0, le=3, description="Urgency 0-3, mirroring the driving theme's urgency."
    )
    theme_ids: list[str] = Field(
        default_factory=list,
        description="Existing theme ids (th_...) this bet addresses. Never invent ids.",
    )
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Feedback ids (fb_...) that justify the bet. Never invent ids.",
    )


class BetProposals(BaseModel):
    """Container schema: the prioritizer emits exactly this JSON object."""

    bets: list[BetProposal] = Field(
        default_factory=list,
        description="3-5 prioritized bets, most urgent first.",
    )
