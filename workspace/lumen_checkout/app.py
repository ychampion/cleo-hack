"""Lumen billing service — checkout pricing for the team-analytics product.

Small but real FastAPI app: a plan catalog and a checkout endpoint that
computes the amount due. All money is integer cents (no float rounding).

Run standalone: `uvicorn workspace.lumen_checkout.app:app --port 9090`
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Lumen Billing", version="2.3.0")

# Plan catalog — prices in cents. `base` is the monthly platform fee,
# `per_seat` the standard monthly seat rate, `max_seats` the plan ceiling.
PLANS: dict[str, dict[str, int]] = {
    "starter": {"base": 0, "per_seat": 1200, "max_seats": 5},
    "team": {"base": 4900, "per_seat": 900, "max_seats": 25},
    "business": {"base": 19900, "per_seat": 700, "max_seats": 500},
}

# Discounted per-seat rates (cents) for volume pricing tiers.
VOLUME_RATES: dict[str, int] = {
    "business-volume": 550,  # business plan at 11+ seats
}


class CheckoutRequest(BaseModel):
    plan: str
    seats: int
    card_token: str


@app.get("/billing/plans")
def list_plans() -> dict:
    """The public plan catalog."""
    return {"plans": PLANS}


@app.post("/billing/checkout")
def checkout(req: CheckoutRequest) -> dict:
    """Price a subscription and confirm the charge against the card token."""
    plan = PLANS.get(req.plan)
    if plan is None:
        raise HTTPException(status_code=404, detail=f"unknown plan: {req.plan!r}")
    if req.seats < 1:
        raise HTTPException(status_code=422, detail="seats must be at least 1")
    if req.seats > plan["max_seats"]:
        raise HTTPException(
            status_code=422,
            detail=f"plan {req.plan!r} supports at most {plan['max_seats']} seats",
        )
    if not req.card_token.strip():
        raise HTTPException(status_code=422, detail="card_token is required")

    per_seat = plan["per_seat"]
    discount_cents = 0

    # ---- v2.3 changelog --------------------------------------------------
    # * NEW: volume pricing for business workspaces above 10 seats — sales
    #   asked for the discounted seat rate to apply automatically at 11+.
    # * Checkout response now includes `discount_cents` so the web UI can
    #   show savings at a glance.
    # ----------------------------------------------------------------------
    if req.plan == "business" and req.seats > 10:
        per_seat = VOLUME_RATES["business_volume"]
        discount_cents = (plan["per_seat"] - per_seat) * req.seats

    amount_due_cents = plan["base"] + per_seat * req.seats
    return {
        "status": "confirmed",
        "plan": req.plan,
        "seats": req.seats,
        "amount_due_cents": amount_due_cents,
        "discount_cents": discount_cents,
        "currency": "usd",
    }
