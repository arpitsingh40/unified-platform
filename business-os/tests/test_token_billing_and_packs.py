"""Backend regression tests for SmartDecigen token-based billing + payments updates.

Covers:
- Auth (demo + founder)
- Packs ordering/amounts/tags + live test_mode flag
- /api/credits new fields
- Turn endpoints (normal + ultra) reserve-and-reconcile token billing
- complete-action token billing
- create-order live Zoho hosted checkout URL + history visibility
- Stale-order auto-fail via Mongo backdating
- 422 mode validation
- 402 insufficient credits
"""
import os
import math
import uuid
import time
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient

# Live-integration suite: needs a deployed backend + seeded demo users + live Zoho.
# Skipped entirely unless REACT_APP_BACKEND_URL is explicitly set.
pytestmark = pytest.mark.skipif(
    not os.environ.get("REACT_APP_BACKEND_URL"),
    reason="live integration suite — set REACT_APP_BACKEND_URL to run",
)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

DEMO_EMAIL = "demo@smartdecigen.com"
DEMO_PASS = "Demo1234!"
ADMIN_EMAIL = "ceo@smartdecigen.com"
ADMIN_PASS = "FounderOS@2026"


# ---------- shared fixtures ----------
@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# Fixture with demo user auth token and user
@pytest.fixture(scope="session")
def demo_auth(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS}, timeout=30)
    assert r.status_code == 200, f"demo login failed: {r.status_code} {r.text}"
    data = r.json()
    return {"token": data["token"], "user": data["user"]}


# Fixture with admin auth token and user
@pytest.fixture(scope="session")
def admin_auth(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    return r.json()


# Helper for Authorization header dict
def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# Fixture with the Mongo database handle
@pytest.fixture(scope="session")
def mongo():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "smartdecigen")]


# ---------- auth ----------
class TestAuth:
    # Demo login returns JWT and credit balance
    def test_demo_login_returns_jwt_and_credits(self, demo_auth):
        assert demo_auth["token"] and isinstance(demo_auth["token"], str)
        u = demo_auth["user"]
        assert u["email"] == DEMO_EMAIL
        assert isinstance(u["credits"], int)
        assert u.get("is_admin") in (False, None)

    # Founder account logs in as admin
    def test_founder_login_is_admin(self, admin_auth):
        assert admin_auth["user"]["is_admin"] is True


# ---------- packs ----------
class TestPacks:
    # Packs endpoint returns live order, amounts, and tags
    def test_packs_order_amounts_tags_live(self, session):
        r = session.get(f"{BASE_URL}/api/payments/packs", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["test_mode"] is False, "expected live mode (ZOHO_TEST_MODE=false)"
        assert body["currency"] == "INR"
        packs = body["packs"]
        ids = [p["pack_id"] for p in packs]
        assert ids == ["pack_10", "pack_100", "pack_500"], f"order wrong: {ids}"
        amounts = {p["pack_id"]: p["amount_inr"] for p in packs}
        assert amounts == {"pack_10": 49, "pack_100": 399, "pack_500": 999}
        tags = {p["pack_id"]: p.get("tag") for p in packs}
        assert tags["pack_10"] == "Try it"
        assert tags["pack_500"] == "Best value"
        assert tags.get("pack_100") in (None,)  # no tag expected


# ---------- /api/credits ----------
class TestCreditsEndpoint:
    # Credits endpoint exposes token billing fields
    def test_credits_includes_token_billing_fields(self, session, demo_auth):
        r = session.get(f"{BASE_URL}/api/credits", headers=_hdr(demo_auth["token"]), timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["credits_per_1k_tokens"] == 2
        assert d["turn_reserve_normal"] == 8
        assert d["turn_reserve_ultra"] == 24
        assert d["assist_reserve"] == 10
        # legacy fields still present
        assert "turn_cost" in d and "ultra_turn_cost" in d


# ---------- token billing helpers ----------
def _seeded_thread_id(session, token):
    r = session.get(f"{BASE_URL}/api/goals", headers=_hdr(token), timeout=15)
    assert r.status_code == 200, r.text
    goals = r.json().get("goals", [])
    active = [g for g in goals if g["status"] == "active"]
    assert active, "demo user must have at least one active seeded thread"
    return active[0]["thread_id"]


# Token cost formula used across billing assertions
def _expected_cost(total_tokens):
    return max(1, math.ceil(total_tokens / 1000) * 2)


# Helper to fetch current credit balance
def _credits(session, token):
    return session.get(f"{BASE_URL}/api/credits", headers=_hdr(token), timeout=15).json()["credits"]


# ---------- /turn normal ----------
class TestTurnNormal:
    # Normal turn deducts exact token cost, not reserve
    def test_turn_normal_token_billing(self, session, demo_auth):
        token = demo_auth["token"]
        tid = _seeded_thread_id(session, token)
        before = _credits(session, token)
        r = session.post(f"{BASE_URL}/api/threads/{tid}/turn",
                         headers=_hdr(token),
                         json={"message": "Quick check-in: did one small thing today.", "mode": "normal"},
                         timeout=120)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert "cost" in body and "tokens" in body
        assert body["mode"] == "normal"
        cost = body["cost"]
        tokens = body["tokens"]
        assert cost == _expected_cost(tokens), f"cost {cost} != formula({tokens}) {_expected_cost(tokens)}"
        after = body["credits"]
        assert after == before - cost, f"net deduction {before-after} should equal cost {cost} (not reserve 8)"
        # sanity: cost should be much less than reserve for typical turn
        assert cost <= 8, f"normal turn cost {cost} should fit inside reserve 8"


# ---------- /turn ultra ----------
class TestTurnUltra:
    # Ultra turn bills tokens on the same formula
    def test_turn_ultra_token_billing(self, session, demo_auth):
        token = demo_auth["token"]
        tid = _seeded_thread_id(session, token)
        before = _credits(session, token)
        r = session.post(f"{BASE_URL}/api/threads/{tid}/turn",
                         headers=_hdr(token),
                         json={"message": "Stuck on positioning. Walk me through the trade-offs.",
                               "mode": "ultra"},
                         timeout=180)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body["mode"] == "ultra"
        cost = body["cost"]
        tokens = body["tokens"]
        assert cost == _expected_cost(tokens)
        after = body["credits"]
        assert after == before - cost


# ---------- /complete-action ----------
class TestCompleteAction:
    # Complete-action endpoint bills tokens and yields artifact
    def test_complete_action_token_billing(self, session, demo_auth):
        token = demo_auth["token"]
        tid = _seeded_thread_id(session, token)
        before = _credits(session, token)
        r = session.post(f"{BASE_URL}/api/threads/{tid}/complete-action",
                         headers=_hdr(token), timeout=180)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert "artifact" in body and body["artifact"]
        cost = body["cost"]
        tokens = body["tokens"]
        assert cost == _expected_cost(tokens)
        after = body["credits"]
        assert after == before - cost


# ---------- payment create-order live ----------
class TestCreateOrderLive:
    # Live Zoho order appears in payment history
    def test_create_order_live_zoho_url_and_history(self, session, demo_auth):
        token = demo_auth["token"]
        r = session.post(f"{BASE_URL}/api/payments/create-order",
                         headers=_hdr(token), json={"pack_id": "pack_10"}, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body["test_mode"] is False
        url = body["checkout_url"]
        assert "hostedcheckout" in url or "payments.zoho" in url, f"unexpected checkout url: {url}"
        order_id = body["order_id"]

        h = session.get(f"{BASE_URL}/api/payments/history", headers=_hdr(token), timeout=15)
        assert h.status_code == 200
        items = h.json()["items"]
        found = next((o for o in items if o["order_id"] == order_id), None)
        assert found, "newly created order missing from history"
        assert found["status"] == "created"
        assert found["amount_inr"] == 49
        assert found["pack_id"] == "pack_10"


# ---------- stale-order auto-fail (backdate via Mongo) ----------
class TestStaleOrderAutoFail:
    # Helper that creates a live pack order
    def _create_order(self, session, token, mongo):
        r = session.post(f"{BASE_URL}/api/payments/create-order",
                         headers=_hdr(token), json={"pack_id": "pack_10"}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()["order_id"]

    # Helper that backdates an order's created_at
    def _backdate(self, mongo, order_id):
        old = datetime.now(timezone.utc) - timedelta(minutes=45)
        res = mongo["payment_orders"].update_one({"order_id": order_id}, {"$set": {"created_at": old}})
        assert res.matched_count == 1, f"backdate failed for {order_id}"

    # Stale orders auto-fail via status endpoint
    def test_status_endpoint_auto_fails_stale(self, session, demo_auth, mongo):
        token = demo_auth["token"]
        oid = self._create_order(session, token, mongo)
        self._backdate(mongo, oid)
        # For live mode, status endpoint will first try Zoho — that's fine, then stale check kicks in.
        r = session.get(f"{BASE_URL}/api/payments/status/{oid}", headers=_hdr(token), timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "failed", f"expected failed got {r.json()}"

    # Stale orders auto-fail via history endpoint
    def test_history_endpoint_auto_fails_stale(self, session, demo_auth, mongo):
        token = demo_auth["token"]
        oid = self._create_order(session, token, mongo)
        self._backdate(mongo, oid)
        r = session.get(f"{BASE_URL}/api/payments/history", headers=_hdr(token), timeout=15)
        assert r.status_code == 200
        items = r.json()["items"]
        found = next((o for o in items if o["order_id"] == oid), None)
        assert found and found["status"] == "failed", f"history did not auto-fail: {found}"


# ---------- validation guards ----------
class TestValidationGuards:
    # Invalid mode returns 422
    def test_turn_invalid_mode_422(self, session, demo_auth):
        token = demo_auth["token"]
        tid = _seeded_thread_id(session, token)
        r = session.post(f"{BASE_URL}/api/threads/{tid}/turn",
                         headers=_hdr(token),
                         json={"message": "hi", "mode": "gibberish"}, timeout=15)
        assert r.status_code == 422, f"expected 422 got {r.status_code} {r.text}"

    def test_402_when_credits_below_reserve(self, session, demo_auth, mongo):
        """Create fresh user via signup, set credits=1 directly in Mongo, attempt normal turn -> 402."""
        email = f"test_lowcredits_{uuid.uuid4().hex[:8]}@example.com"
        r = session.post(f"{BASE_URL}/api/auth/signup",
                         json={"email": email, "password": "Pass1234!", "name": "TEST low"}, timeout=15)
        assert r.status_code == 200, r.text
        new_token = r.json()["token"]
        new_user_id = r.json()["user"]["id"]
        # create a goal (uses 8 reserve, but they have 100 from signup - fine)
        g = session.post(f"{BASE_URL}/api/goals",
                        headers=_hdr(new_token),
                        json={"title": "TEST low credit goal", "why_now": "Testing 402 on insufficient credits"},
                        timeout=120)
        assert g.status_code == 200, g.text
        tid = g.json()["thread"]["thread_id"]
        # force credits to 1
        mongo["users"].update_one({"id": new_user_id}, {"$set": {"credits": 1}})
        r2 = session.post(f"{BASE_URL}/api/threads/{tid}/turn",
                          headers=_hdr(new_token),
                          json={"message": "should fail with 402", "mode": "normal"}, timeout=30)
        assert r2.status_code == 402, f"expected 402 got {r2.status_code} {r2.text}"
        # cleanup
        mongo["threads"].delete_many({"user_id": new_user_id})
        mongo["users"].delete_one({"id": new_user_id})


# ---------- refund-on-LLM-failure semantics (best-effort check of message wording) ----------
class TestLLMFailureMessage:
    def test_502_message_says_not_charged(self):
        """We can't easily force a 502 here without breaking the API key, so we only assert that
        the documented user-facing copy lives in the source — verified by reading server.py."""
        with open("/app/backend/server.py", "r") as f:
            src = f.read()
        assert "You were not charged" in src
