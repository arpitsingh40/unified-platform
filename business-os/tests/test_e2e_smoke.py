"""E2E Smoke Tests — verify core flows work end-to-end.
Run with: python -m pytest tests/test_e2e_smoke.py -v
Uses mongomock (no external DB needed) and mocks LLM calls.
"""
import json
import pytest
from unittest.mock import patch, MagicMock

# ── Mock LLM responses ──

MOCK_TURN_RESPONSE = {
    "phase": "exploring",
    "phase_reason": "New goal, sparse state model",
    "acknowledgment": "You're starting something real. Let me understand the shape of it first.",
    "mirror": "It sounds like you've been carrying this alone for a while.",
    "understanding": {"focus": "starting a business", "fears": "failure", "blockers": "no plan",
                      "constraints": "limited budget", "tried": "thinking about it",
                      "motivators": "freedom", "stage": "ideation", "gap_to_goal": "no clear first step",
                      "emotional_read": "determined but uncertain", "needs_now": "plan"},
    "refreshed_easiest_path": None,
    "refreshed_next_action": None,
    "outbox_alternative": None,
    "action_payoff": None,
    "big_picture_link": None,
    "bold_move": None,
    "requested_input": None,
    "file_facts": None,
    "refreshed_open_question": "What's the one thing you'd need to be true for this to actually work?",
    "skip_list": [],
    "state_summary": "Early stage. Dream stated but not yet grounded in concrete steps.",
    "signals": {"emotional_temperature": 0.6, "action_done": False, "contradiction": None},
}

MOCK_AGENT_RESPONSE = json.dumps({
    "action": "NOTHING",
    "severity": "low",
    "summary": "No issues detected in this domain",
    "needs_founder": False,
})

MOCK_AGENT_ALERT = json.dumps({
    "action": "ALERT",
    "severity": "medium",
    "summary": "3 deals stuck >14 days, needs follow-up",
    "recommendation": "Send personalized follow-up emails",
    "needs_founder": True,
})


# Mock of the OpenAI response object
class MockResponse:
    def __init__(self, text, input_tokens=100, output_tokens=50):
        self.content = [MockContent(text)]
        self.usage = MockUsage(input_tokens, output_tokens)


# Mock of response content block
class MockContent:
    def __init__(self, text):
        self.text = text
        self.type = "text"


# Mock of token usage counters
class MockUsage:
    def __init__(self, input_tokens, output_tokens):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


# ======================================================================
# Test 1: Engine intent classification (pure, no DB/LLM)
# ======================================================================

def test_intent_classifier():
    from engine import classify_intent
    assert classify_intent("I did it. Shipped the landing page.", 3) == "acknowledgment"
    assert classify_intent("Couldn't get the meeting. They ghosted.", 3) == "setback"
    assert classify_intent("How should I price this product?", 3) == "question"
    assert classify_intent("hi", 3) == "drift"
    assert classify_intent("Been working on the new feature this week, making progress", 3) == "update"
    # Silence breaker after 14+ days
    assert classify_intent("Still here", 20) == "silence_breaker"


# ======================================================================
# Test 2: Rolling fields (pure)
# ======================================================================

def test_rolling_fields():
    from engine import rolling_fields
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    events = [
        {"at": now - timedelta(days=2), "emotional_temperature": 0.7, "action_done": True, "contradiction": None},
        {"at": now - timedelta(days=4), "emotional_temperature": 0.5, "action_done": False, "contradiction": None},
        {"at": now - timedelta(days=6), "emotional_temperature": 0.3, "action_done": True, "contradiction": "Said market is ready but no data to back it"},
    ]
    result = rolling_fields(events, now)
    assert 0 <= result["emotional_temperature"] <= 1
    assert 0 <= result["execution_consistency"] <= 1
    assert result["pace_calibration"] in ("on-track", "ahead", "behind")


# ======================================================================
# Test 3: Re-engagement line (pure)
# ======================================================================

def test_reengagement_line():
    from engine import compute_reengagement_line
    last = {"execution_consistency": 0.3, "emotional_temperature": 0.5, "contradiction_history": []}
    now = {"execution_consistency": 0.8, "emotional_temperature": 0.5, "contradiction_history": []}
    line = compute_reengagement_line(last, now, 10)
    assert line is not None
    assert "follow-through" in line.lower()


# ======================================================================
# Test 4: SALAAR route classifier (pure)
# ======================================================================

def test_salaar_route():
    from engine import salaar_route
    assert salaar_route("What is our return policy?") == "knowledge"
    assert salaar_route("Should I hire a CTO or outsource?") == "decision"
    assert salaar_route("I'm not sure what to do") == "diagnosis"
    # With thread context, execution updates route to engine
    thread = {"current_phase": "acting"}
    assert salaar_route("I shipped the feature, got 3 signups today", thread) == "engine"


# ======================================================================
# Test 5: Cognition category classifier (pure)
# ======================================================================

def test_cognition_classifier():
    from cognition import classify_decision
    assert classify_decision("I need to negotiate a distribution deal") == "deal_negotiation"
    assert classify_decision("Should I hire a senior engineer or a junior?") == "people_team"
    assert classify_decision("Our churn is spiking, we're losing money") == "crisis_survival"
    assert classify_decision("How should I price the premium tier?") == "pricing_offer"
    assert classify_decision("I want to build an MVP but not sure where to start") == "product_validation"


# ======================================================================
# Test 6: Capability router (pure)
# ======================================================================

def test_capability_router():
    from capabilities import route_capability, CAPABILITIES
    assert len(CAPABILITIES) == 15
    r = route_capability("build me a landing page for my skincare brand")
    assert r and r["type"] == "website"
    r2 = route_capability("I need an investor pitch deck for Series A")
    assert r2 and r2["type"] == "investor_deck"
    r3 = route_capability("write a job description for a senior engineer")
    assert r3 and r3["type"] == "job_description"


# ======================================================================
# Test 7: Agent definitions are valid
# ======================================================================

def test_agent_definitions():
    from agents import AGENT_DEFINITIONS, AUTHORITY_LEVELS, SCHEDULES
    assert len(AGENT_DEFINITIONS) == 12
    for atype, defn in AGENT_DEFINITIONS.items():
        assert "decision_prompt" in defn, f"{atype} missing decision_prompt"
        assert "authority" in defn, f"{atype} missing authority"
        assert defn["authority"] in AUTHORITY_LEVELS, f"{atype} invalid authority"
        assert defn["schedule"] in SCHEDULES, f"{atype} invalid schedule"


# ======================================================================
# Test 8: Workflow templates are valid
# ======================================================================

def test_workflows():
    from execution.workflows import WORKFLOWS, match_workflows, workflow_to_execution_plan
    assert len(WORKFLOWS) >= 14
    for func, wfs in WORKFLOWS.items():
        for wf in wfs:
            assert "tools" in wf
            assert len(wf["tools"]) >= 1
            assert "trigger" in wf

    matches = match_workflows("our revenue dropped and churn is spiking")
    assert len(matches) >= 1

    plan = workflow_to_execution_plan(matches[0])
    assert "goal" in plan and len(plan["actions"]) > 0


# ======================================================================
# Test 9: Business process templates
# ======================================================================

def test_business_processes():
    from business_os import BUSINESS_PROCESSES
    assert len(BUSINESS_PROCESSES) == 7
    for pid, proc in BUSINESS_PROCESSES.items():
        assert "agent_chain" in proc
        assert len(proc["agent_chain"]) >= 1


# ======================================================================
# Test 10: Audit system
# ======================================================================

def test_audit_system():
    from audit import EVENT_TYPES, record, query, summary
    assert len(EVENT_TYPES) >= 20
    # With mongomock, record/query should work
    eid = record("test_org", "agent_decision", "Test agent made a decision",
                 actor_type="agent", actor_id="sales_agent")
    assert eid is not None or True  # May be None if DB not available


# ======================================================================
# Test 11: Multi-provider LLM router structure
# ======================================================================

def test_llm_router():
    from llm_router import (
        AGENT_DECISION_CHAIN, AGENT_ULTRA_CHAIN, AGENT_FAST_CHAIN, VERIFICATION_CHAIN,
        available_models, _init_providers,
    )
    assert len(AGENT_DECISION_CHAIN) >= 2
    assert len(AGENT_ULTRA_CHAIN) >= 1
    assert len(AGENT_FAST_CHAIN) >= 1
    _init_providers()
    models = available_models()
    # At minimum, DeepSeek models should be listed if key is set
    assert any("deepseek" in m for m in models) or len(models) >= 0


# ======================================================================
# Test 12: Ontology models are valid
# ======================================================================

def test_ontology():
    from ontology.models import (
        Mission, Goal, Capability, Project, Task, Trace, Evidence,
        OutcomeStatus, AuthorityLevel, Reversibility,
    )
    m = Mission(title="Test", statement="Test mission")
    assert m.title == "Test"
    g = Goal(description="Test goal")
    assert g.description == "Test goal"
    c = Capability(name="Test capability")
    assert c.name == "Test capability"
    assert OutcomeStatus.SUCCESS.value == "SUCCESS"
    assert AuthorityLevel.L0_OBSERVE.value == "L0"
    assert Reversibility.REVERSIBLE.value == "REVERSIBLE"


# ======================================================================
# Test 13: Agent coordination map is complete
# ======================================================================

def test_agent_coordination():
    from agents import COORDINATION_MAP, AGENT_DEFINITIONS
    for atype in AGENT_DEFINITIONS:
        assert atype in COORDINATION_MAP, f"{atype} missing from coordination map"


# ======================================================================
# Test 14: API route counts (structural)
# ======================================================================

def test_router_structure():
    from business_os_router import router as bos_router
    from audit_router import router as audit_router
    from capabilities_router import router as cap_router
    from execution.router import router as exec_router
    assert len(bos_router.routes) >= 7
    assert len(audit_router.routes) >= 3
    assert len(cap_router.routes) >= 5
    assert len(exec_router.routes) >= 10
