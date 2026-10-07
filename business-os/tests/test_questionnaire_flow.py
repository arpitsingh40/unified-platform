"""Backend tests for questionnaire + signup credits flow.
Covers: GET /api/config, signup credits/flag, GET/POST /api/user/questionnaire idempotency,
validation, auth requirement, and goal/turn regression.
"""
import os
import time
import requests
import pytest

import pytest

# Resolve backend base URL from env or frontend .env
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except FileNotFoundError:
        pass

if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set and no .env found — skipping integration tests", allow_module_level=True)

API = f"{BASE_URL}/api"


# Helper that signs up a fresh QA user
def _signup():
    ts = int(time.time() * 1000)
    email = f"qa_{ts}@test.com"
    r = requests.post(f"{API}/auth/signup", json={"email": email, "password": "abcdef123", "name": "QA Bot"}, timeout=15)
    assert r.status_code == 200, f"signup failed: {r.status_code} {r.text}"
    return email, r.json()


# Fixture with a freshly signed-up user token
@pytest.fixture(scope="module")
def fresh_user():
    email, data = _signup()
    return {"email": email, "token": data["token"], "user": data["user"]}


# Fixture returning Authorization headers
@pytest.fixture
def auth_headers(fresh_user):
    return {"Authorization": f"Bearer {fresh_user['token']}"}


# ---- /api/config public ----
def test_config_signup_credits():
    r = requests.get(f"{API}/config", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data.get("signup_credits") == 50, f"expected 50, got {data}"


# ---- signup response shape ----
def test_signup_returns_50_credits_and_questionnaire_false(fresh_user):
    u = fresh_user["user"]
    assert u["credits"] == 50
    assert u["questionnaire_completed"] is False
    assert "id" in u and "email" in u


# ---- /api/auth/me ----
def test_auth_me_fresh_user(fresh_user, auth_headers):
    r = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    me = r.json()
    assert me["credits"] == 50
    assert me["questionnaire_completed"] is False
    assert me["email"] == fresh_user["email"]


# ---- GET /api/user/questionnaire pre-completion ----
def test_get_questionnaire_pre_completion(auth_headers):
    r = requests.get(f"{API}/user/questionnaire", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["completed"] is False
    assert data["bonus_credits"] == 100
    assert data["answers"] is None


# ---- Auth required ----
def test_questionnaire_requires_auth():
    r = requests.post(f"{API}/user/questionnaire", json={
        "dream": "abc", "capacity": "abc", "advantage": "abc", "potential": "abc",
    }, timeout=10)
    assert r.status_code in (401, 403)


# ---- Validation: missing field / empty ----
def test_questionnaire_validation_short_field(auth_headers):
    r = requests.post(f"{API}/user/questionnaire", headers=auth_headers, json={
        "dream": "", "capacity": "abcd", "advantage": "abcd", "potential": "abcd",
    }, timeout=10)
    assert r.status_code == 422


# Missing required field triggers 422
def test_questionnaire_validation_missing_field(auth_headers):
    r = requests.post(f"{API}/user/questionnaire", headers=auth_headers, json={
        "dream": "abcd", "capacity": "abcd", "advantage": "abcd",
    }, timeout=10)
    assert r.status_code == 422


# ---- POST /api/user/questionnaire first completion + idempotency ----
def test_first_completion_grants_100_credits(fresh_user, auth_headers):
    payload = {
        "dream": "Build a calm studio of my own.",
        "capacity": "8 hours a week, 50k risk capital.",
        "advantage": "Six years in the industry plus warm network.",
        "potential": "Go-to brand storyteller in India in 2 years.",
    }
    r = requests.post(f"{API}/user/questionnaire", headers=auth_headers, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["first_completion"] is True
    assert d["credits_added"] == 100
    assert d["credits"] == 150  # 50 signup + 100 bonus
    assert d["answers"]["dream"].startswith("Build a calm")


# Re-submitting the questionnaire adds no more credits
def test_second_post_is_idempotent(auth_headers):
    payload = {
        "dream": "Updated dream text here.",
        "capacity": "Updated capacity text.",
        "advantage": "Updated advantage text.",
        "potential": "Updated potential text.",
    }
    # Snapshot credits first
    me = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=10).json()
    before = me["credits"]
    r = requests.post(f"{API}/user/questionnaire", headers=auth_headers, json=payload, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["first_completion"] is False
    assert d["credits_added"] == 0
    assert d["credits"] == before, f"balance changed: {before} -> {d['credits']}"
    assert d["answers"]["dream"] == "Updated dream text here."


# Completed questionnaire is reflected in GET
def test_get_after_completion_shows_completed_and_answers(auth_headers):
    r = requests.get(f"{API}/user/questionnaire", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["completed"] is True
    assert d["answers"]["dream"] == "Updated dream text here."


# /auth/me reflects questionnaire completion
def test_auth_me_after_completion(auth_headers):
    r = requests.get(f"{API}/auth/me", headers=auth_headers, timeout=10)
    assert r.status_code == 200
    assert r.json()["questionnaire_completed"] is True


# ---- Regression: POST /api/goals still works after questionnaire ----
def test_create_goal_after_questionnaire(auth_headers):
    body = {"title": "Ship MVP v1", "why_now": "Because I want to launch this month and validate fast."}
    r = requests.post(f"{API}/goals", headers=auth_headers, json=body, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    # Verify response shape
    for k in ("thread", "acknowledgment", "credits", "cost", "tokens"):
        assert k in d, f"missing key {k}"
    assert d["thread"]["goal"] == "Ship MVP v1"
    assert isinstance(d["credits"], int)
    assert d["credits"] >= 0
    assert d["cost"] >= 1
    # Stash thread_id for next test
    pytest.thread_id = d["thread"]["thread_id"]


# Turns still work after questionnaire completion
def test_turn_after_questionnaire(auth_headers):
    thread_id = getattr(pytest, "thread_id", None)
    if not thread_id:
        pytest.skip("no thread from previous test")
    body = {"message": "I have two hours this evening — what do I tackle?", "mode": "normal"}
    r = requests.post(f"{API}/threads/{thread_id}/turn", headers=auth_headers, json=body, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    for k in ("thread", "acknowledgment", "credits", "cost", "tokens", "intent"):
        assert k in d
