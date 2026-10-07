import pytest
from datetime import datetime, timezone, timedelta
from engine import classify_intent, rolling_fields, compute_reengagement_line, _extract_json
from server import token_cost


# Intent classifier unit tests
class TestClassifyIntent:
    # Acknowledgment phrases route to acknowledgment intent
    def test_acknowledgment(self):
        assert classify_intent("I did it!", 1) == "acknowledgment"
        assert classify_intent("completed the call", 1) == "acknowledgment"
        assert classify_intent("shipped it yesterday", 1) == "acknowledgment"

    # Failure phrases route to setback intent
    def test_setback(self):
        assert classify_intent("I couldn't finish", 1) == "setback"
        assert classify_intent("failed again", 1) == "setback"
        assert classify_intent("stuck on this", 1) == "setback"

    # Question phrases route to question intent
    def test_question(self):
        assert classify_intent("How should I price this?", 1) == "question"
        assert classify_intent("What do you think?", 1) == "question"
        assert classify_intent("Should I hire?", 1) == "question"

    # Long silence triggers silence_breaker intent
    def test_silence_breaker(self):
        assert classify_intent("Hey, I'm back", 14) == "silence_breaker"
        assert classify_intent("Long time no talk", 20) == "silence_breaker"

    # Generic chat falls through to drift intent
    def test_drift(self):
        assert classify_intent("Hi", 1) == "drift"
        assert classify_intent("ok", 1) == "drift"

    # Progress details route to update intent
    def test_update(self):
        assert classify_intent("I talked to three customers and they all said the same thing", 1) == "update"


# Rolling state-field computation tests
class TestRollingFields:
    # Empty event list yields neutral defaults
    def test_empty_events(self):
        result = rolling_fields([], datetime.now(timezone.utc))
        assert result["emotional_temperature"] == 0.5
        assert result["execution_consistency"] == 0.5

    # All actions done yields full consistency
    def test_good_consistency(self, sample_events):
        now = datetime.now(timezone.utc)
        events = [
            {"at": now - timedelta(hours=1), "emotional_temperature": 0.7,
             "action_assigned": True, "action_done": True, "contradiction": None},
            {"at": now - timedelta(hours=2), "emotional_temperature": 0.6,
             "action_assigned": True, "action_done": True, "contradiction": None},
            {"at": now - timedelta(hours=3), "emotional_temperature": 0.5,
             "action_assigned": True, "action_done": True, "contradiction": None},
        ]
        result = rolling_fields(events, now)
        assert result["execution_consistency"] == 1.0

    # Missed actions yield zero consistency and behind pace
    def test_poor_consistency(self):
        now = datetime.now(timezone.utc)
        events = [
            {"at": now - timedelta(hours=1), "emotional_temperature": 0.3,
             "action_assigned": True, "action_done": False, "contradiction": None},
            {"at": now - timedelta(hours=2), "emotional_temperature": 0.2,
             "action_assigned": True, "action_done": False, "contradiction": None},
        ]
        result = rolling_fields(events, now)
        assert result["execution_consistency"] == 0.0
        assert result["pace_calibration"] == "behind"

    # Temperature average lands inside fixture range
    def test_emotional_temperature_average(self, sample_events):
        now = datetime.now(timezone.utc)
        result = rolling_fields(sample_events, now)
        assert 0.4 <= result["emotional_temperature"] <= 0.6


# Re-engagement line generation tests
class TestReengagementLine:
    # No re-engagement line within 7 days
    def test_no_reengagement_under_7_days(self):
        last_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.5,
                     "pace_calibration": "on-track", "contradiction_history": [],
                     "summary_line": "Making progress"}
        now_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.5,
                    "pace_calibration": "on-track", "contradiction_history": []}
        result = compute_reengagement_line(last_snap, now_snap, 5)
        assert result is None

    # Execution change after 7+ days triggers a line
    def test_reengagement_with_execution_change(self):
        last_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.5,
                     "pace_calibration": "on-track", "contradiction_history": [],
                     "summary_line": "Making progress"}
        now_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.8,
                    "pace_calibration": "ahead", "contradiction_history": []}
        result = compute_reengagement_line(last_snap, now_snap, 10)
        assert result is not None
        assert "days away" in result

    # Unchanged snapshots produce no line
    def test_no_change_no_reengagement(self):
        last_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.5,
                     "pace_calibration": "on-track", "contradiction_history": [],
                     "summary_line": "Making progress"}
        now_snap = {"emotional_temperature": 0.5, "execution_consistency": 0.5,
                    "pace_calibration": "on-track", "contradiction_history": []}
        result = compute_reengagement_line(last_snap, now_snap, 10)
        assert result is None


# JSON extraction helper tests
class TestExtractJson:
    # Bare JSON passes through unchanged
    def test_simple_json(self):
        assert _extract_json('{"key": "value"}') == '{"key": "value"}'

    # Fenced JSON block is unwrapped
    def test_json_with_code_fence(self):
        assert _extract_json('```json\n{"key": "value"}\n```') == '{"key": "value"}'

    # Leading prose is stripped
    def test_json_with_leading_text(self):
        result = _extract_json('Here is the result: {"key": "value"}')
        assert result == '{"key": "value"}'

    # Trailing prose is stripped
    def test_json_with_trailing_text(self):
        result = _extract_json('{"key": "value"} and some trailing text')
        assert result == '{"key": "value"}'


# Token cost pricing tests
class TestTokenCost:
    # Cost never drops below one credit
    def test_minimum_one_credit(self):
        assert token_cost(0, 0) == 1
        assert token_cost(100, 50) >= 1

    # Larger token counts cost at least as much
    def test_proportional_cost(self):
        cost_1k = token_cost(500, 500)
        cost_2k = token_cost(1000, 1000)
        assert cost_2k >= cost_1k
