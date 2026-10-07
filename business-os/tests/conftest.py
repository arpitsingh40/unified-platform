import os
import pytest
from datetime import datetime, timezone


# Set default env vars for every test run
@pytest.fixture(autouse=True)
def setup_env():
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("TURN_COST", "5")
    os.environ.setdefault("SIGNUP_CREDITS", "100")
    os.environ.setdefault("MONGO_URL", "")
    os.environ.setdefault("LLM_PROVIDER", "deepseek")
    os.environ.setdefault("DEEPSEEK_API_KEY", "test-key")
    yield


# Fixture with a minimal active thread document
@pytest.fixture
def sample_thread():
    return {
        "thread_id": "test-thread-1",
        "user_id": "test-user-1",
        "goal": "Grow SaaS revenue to ₹10L ARR",
        "why_now": "Running out of runway in 6 months",
        "status": "active",
        "current_phase": "exploring",
        "current_state_summary": "Just starting out",
        "current_open_question": "What's the first step?",
        "current_easiest_path": "(none yet)",
        "current_next_action": "(none yet)",
        "opened_at": datetime.now(timezone.utc),
        "messages": [],
        "rolling": {"emotional_temperature": 0.5, "execution_consistency": 0.5, "pace_calibration": "on-track"},
    }


# Fixture with a minimal user document
@pytest.fixture
def sample_user():
    return {
        "id": "test-user-1",
        "email": "founder@test.com",
        "name": "Test Founder",
        "credits": 100,
        "is_admin": False,
        "country": "India",
        "city": "Mumbai",
    }


# Fixture with sample substrate events
@pytest.fixture
def sample_events():
    return [
        {"at": datetime.now(timezone.utc), "emotional_temperature": 0.6,
         "action_assigned": True, "action_done": True, "contradiction": None},
        {"at": datetime.now(timezone.utc), "emotional_temperature": 0.4,
         "action_assigned": True, "action_done": False, "contradiction": "Fear of pricing too high"},
    ]
