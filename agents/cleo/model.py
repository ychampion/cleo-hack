"""Shared Gemini model factory with 429 retry/backoff.

WHY a ``Gemini`` object instead of a bare model-id string: burst-y stages (the
parallel ingest fan-out especially) can trip ``429 RESOURCE_EXHAUSTED`` on
rate-limited keys (free-tier keys allow only 5 requests/min on
gemini-3.5-flash). The ADK-documented mitigation is ``HttpRetryOptions`` on the
model object, which makes every ``LlmAgent`` resilient to transient quota
errors without per-call handling. The model id itself stays env-driven
(``CLEO_MODEL``, default ``gemini-3.5-flash``) per CONTRACTS §0.
"""

from __future__ import annotations

import os

from google.adk.models.google_llm import Gemini
from google.genai import types


def cleo_model() -> Gemini:
    """Retry-hardened Gemini model shared by every agent in the tree."""
    return Gemini(
        model=os.environ.get("CLEO_MODEL", "gemini-3.5-flash"),
        retry_options=types.HttpRetryOptions(
            initial_delay=float(os.environ.get("CLEO_RETRY_INITIAL_DELAY", "10")),
            attempts=int(os.environ.get("CLEO_RETRY_ATTEMPTS", "6")),
        ),
    )
