"""Checkout pricing suite — the coder's objective function (CONTRACTS §13).

The business-plan volume-pricing cases (12 and 30 seats) FAIL while the v2.3
regression is present and pass once it is fixed. The fix must happen in
app.py — these tests are the acceptance criteria and must not be edited.

Run: `python -m pytest workspace/lumen_checkout/tests -q` (repo root).
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from workspace.lumen_checkout.app import app  # noqa: E402

# raise_server_exceptions=False: an unhandled exception surfaces as the HTTP
# 500 a real client would see, instead of aborting the test with a traceback.
client = TestClient(app, raise_server_exceptions=False)


def _checkout(plan: str, seats: int) -> dict | None:
    resp = client.post(
        "/billing/checkout",
        json={"plan": plan, "seats": seats, "card_token": "tok_visa"},
    )
    assert resp.status_code == 200, f"{plan}/{seats} seats -> HTTP {resp.status_code}"
    return resp.json()


def _assert_shape(body: dict) -> None:
    assert body["status"] == "confirmed"
    assert body["currency"] == "usd"
    assert isinstance(body["amount_due_cents"], int)
    assert isinstance(body["discount_cents"], int)
    assert set(body) == {
        "status",
        "plan",
        "seats",
        "amount_due_cents",
        "discount_cents",
        "currency",
    }


def test_team_plan_checkout():
    body = _checkout("team", 5)
    _assert_shape(body)
    assert body["amount_due_cents"] == 4900 + 900 * 5  # 9400
    assert body["discount_cents"] == 0


def test_business_plan_at_volume_threshold():
    # 10 seats is the last standard-rate tier — no volume pricing involved.
    body = _checkout("business", 10)
    _assert_shape(body)
    assert body["amount_due_cents"] == 19900 + 700 * 10  # 26900
    assert body["discount_cents"] == 0


def test_business_plan_12_seats_gets_volume_rate():
    # FAILS on the v2.3 regression (HTTP 500); passes once checkout prices
    # 11+ business seats at the discounted 550c rate.
    body = _checkout("business", 12)
    _assert_shape(body)
    assert body["amount_due_cents"] == 19900 + 550 * 12  # 26500
    assert body["discount_cents"] == (700 - 550) * 12  # 1800


def test_business_plan_30_seats_gets_volume_rate():
    body = _checkout("business", 30)
    _assert_shape(body)
    assert body["amount_due_cents"] == 19900 + 550 * 30  # 36400
    assert body["discount_cents"] == (700 - 550) * 30  # 4500


def test_checkout_validation():
    assert (
        client.post(
            "/billing/checkout",
            json={"plan": "enterprise", "seats": 3, "card_token": "tok_visa"},
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/billing/checkout",
            json={"plan": "team", "seats": 0, "card_token": "tok_visa"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/billing/checkout",
            json={"plan": "starter", "seats": 99, "card_token": "tok_visa"},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/billing/checkout",
            json={"plan": "team", "seats": 3, "card_token": "  "},
        ).status_code
        == 422
    )
