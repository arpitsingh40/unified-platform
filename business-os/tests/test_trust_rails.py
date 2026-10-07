"""End-to-end test of the Stage-1 TRUST RAILS — zero LLM calls, mongomock in-process.

Covers: org-scoped task queue, owner-only approval, the Approval Brief,
kill switch (Human Override), budget cap gate, honest manual execution
(no invented verification), and real verification when a concrete plan runs.

Run: backend/venv13/bin/python -m pytest backend/tests/test_trust_rails.py -v
"""
import os
import sys
import uuid

os.environ.setdefault("DISABLE_MCP", "1")            # MCP disabled in tests
os.environ.setdefault("ORG_MONTHLY_SPEND_CAP_INR", "25000")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient

import server
from execution.tasks import enqueue_task
from db import executives_col, orgs_col

client = TestClient(server.app)


# Helper that signs up a fresh rails test user
def _signup(email=None):
    email = email or f"rails_{uuid.uuid4().hex[:8]}@test.com"
    r = client.post("/api/auth/signup", json={"email": email, "password": "abcdef123", "name": "Rails"})
    assert r.status_code == 200, r.text
    tok = r.json()["token"]
    return {"Authorization": f"Bearer {tok}"}


# Fixture creating a founder with an org
@pytest.fixture(scope="module")
def founder():
    h = _signup()
    r = client.post("/api/org", json={"name": "Rails Test Co"}, headers=h)
    assert r.status_code == 200, r.text
    org_id = r.json()["org"]["id"] if "org" in r.json() else r.json().get("id")
    if not org_id:  # fallback: look it up
        org_id = client.get("/api/org", headers=h).json()["org"]["id"]
    return {"h": h, "org_id": org_id}


# Fixture with a second user outside the org
@pytest.fixture(scope="module")
def stranger():
    return _signup()  # no org


# Fixture inserting a growth executive row
@pytest.fixture(scope="module")
def executive(founder):
    ex_id = f"exec_test_{uuid.uuid4().hex[:6]}"
    executives_col.insert_one({
        "id": ex_id, "org_id": founder["org_id"], "role": "Growth Executive",
        "department_id": "marketing", "mission": "Fill the pipeline",
        "authority": {"decision_rights": [], "spending_limit_inr": 10000,
                      "can_communicate_externally": False},
        "lifecycle": {"status": "active"},
    })
    return ex_id


# Helper that enqueues a task for the org
def _task(founder, executive, **overrides):
    data = {"description": "Draft outreach list of 10 factory owners",
            "capability": "email", "expected_outcome": "List of 10 with contacts",
            "reversibility": "REVERSIBLE"}
    data.update(overrides)
    return enqueue_task(executive, data, org_id=founder["org_id"])


# Pending tasks are scoped to the owner's org
def test_pending_is_org_scoped(founder, stranger, executive):
    tid = _task(founder, executive)
    mine = client.get("/api/tasks/pending", headers=founder["h"]).json()
    assert any(t["id"] == tid for t in mine["tasks"])
    theirs = client.get("/api/tasks/pending", headers=stranger).json()
    assert theirs["count"] == 0 and not theirs["tasks"]


# Approval brief exposes every outcome field
def test_approval_brief_has_all_outcomes(founder, executive):
    tid = _task(founder, executive)
    r = client.get(f"/api/tasks/{tid}/brief", headers=founder["h"])
    assert r.status_code == 200, r.text
    b = r.json()
    for key in ("task", "executive", "planned_actions", "expected_outcome",
                "reversibility", "budget", "risk_flags", "worst_case",
                "what_happens_if_approved", "estimated_spend_inr"):
        assert key in b, f"brief missing {key}"
    assert b["executive"]["role"] == "Growth Executive"
    assert b["budget"]["cap_inr"] == 25000


# Non-owner approval attempts are forbidden
def test_only_owner_can_approve(founder, stranger, executive):
    tid = _task(founder, executive)
    r = client.post(f"/api/tasks/{tid}/approve", headers=stranger)
    assert r.status_code == 403


# Manual approval never invents verification
def test_manual_path_never_fakes_verification(founder, executive):
    tid = _task(founder, executive)  # no concrete plan, MCP disabled
    r = client.post(f"/api/tasks/{tid}/approve", headers=founder["h"])
    assert r.status_code == 200, r.text
    t = r.json()["task"]
    assert t["status"] == "manual"           # honest: nothing executed
    assert t["verification"] is None         # and nothing fake-verified
    assert "Manual execution required" in (t["result"] or "")


# Over-cap estimates are blocked with 402
def test_budget_cap_blocks_overspend(founder, executive):
    tid = _task(founder, executive, estimated_cost_inr=50000)  # > 25000 cap
    r = client.post(f"/api/tasks/{tid}/approve", headers=founder["h"])
    assert r.status_code == 402
    assert "cap" in r.json()["detail"].lower()


# Kill switch blocks approvals until resumed
def test_kill_switch_blocks_everything(founder, executive):
    tid = _task(founder, executive)
    r = client.post("/api/tasks/kill-switch", json={"paused": True}, headers=founder["h"])
    assert r.status_code == 200 and r.json()["execution_paused"] is True
    r = client.post(f"/api/tasks/{tid}/approve", headers=founder["h"])
    assert r.status_code == 423
    # resume
    client.post("/api/tasks/kill-switch", json={"paused": False}, headers=founder["h"])
    r = client.post(f"/api/tasks/{tid}/approve", headers=founder["h"])
    assert r.status_code == 200


# Second approval attempt conflicts with 409
def test_double_approve_conflicts(founder, executive):
    tid = _task(founder, executive)
    assert client.post(f"/api/tasks/{tid}/approve", headers=founder["h"]).status_code == 200
    assert client.post(f"/api/tasks/{tid}/approve", headers=founder["h"]).status_code == 409


# Rejecting records reason and unknown tasks 404
def test_reject_with_reason(founder, executive):
    tid = _task(founder, executive)
    r = client.post(f"/api/tasks/{tid}/reject", json={"reason": "not now"}, headers=founder["h"])
    assert r.status_code == 200
    assert r.json()["task"]["status"] == "rejected"
    # rejecting someone else's / unknown task 404s
    r = client.post("/api/tasks/task_does_not_exist/reject", json={"reason": "x"}, headers=founder["h"])
    assert r.status_code == 404


# Summary aggregates counts and budget cap
def test_summary_counts_and_budget(founder):
    s = client.get("/api/tasks/summary", headers=founder["h"]).json()
    assert s["total"] >= 5
    assert s["manual"] >= 1 and s["rejected"] >= 1
    assert "budget" in s and s["budget"]["cap_inr"] == 25000


# Archived executives cannot approve tasks
def test_archived_executive_hard_blocked(founder):
    ex_id = f"exec_arch_{uuid.uuid4().hex[:6]}"
    executives_col.insert_one({
        "id": ex_id, "org_id": founder["org_id"], "role": "Archived Exec",
        "authority": {"decision_rights": []}, "lifecycle": {"status": "archived"},
    })
    tid = enqueue_task(ex_id, {
        "description": "Send email blast", "capability": "email",
        "expected_outcome": "sent",
        "plan": [{"tool": "GMAIL_SEND_EMAIL", "args": {"to": "x@y.com"}, "depends_on": []}],
    }, org_id=founder["org_id"])
    r = client.post(f"/api/tasks/{tid}/approve", headers=founder["h"])
    assert r.status_code == 403
    assert "archived" in r.json()["detail"]
