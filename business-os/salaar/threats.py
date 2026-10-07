"""SALAAR — The Shadow Agent. Awareness → Action → People → Shadow.

Phase 1: Event bus — every system action emits events SALAAR subscribes to.
Phase 2: Threat detection — scans events against 169 book lenses + business rules.
Phase 3: Pattern memory — remembers threat→outcome pairs, detects repeats.
Phase 4: Action engine — execute/recommend/escalate/block on L0-L5 gradient.
Phase 5: People graph — profiles every person around the founder.
Phase 6: Behavior scanner — psychology lenses applied to people patterns.
Phase 7: Insight generator — evidence, not conclusions.

SALAAR is not a cron job. It's a continuous scanner that runs underneath
every interaction, detecting threats before the founder sees them,
acting within authority boundaries, and surfacing only what needs
the founder's judgment.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from db import (
    db, orgs_col, members_col, users_col, tasks_col, threads_col,
    telemetry_col, decisions_col, plans_col,
)

log = logging.getLogger("salaar")

# SALAAR's MongoDB collections: events, threats, memory, people, actions.
SALAAR_EVENTS_COL = db["salaar_events"] if db is not None else None
SALAAR_THREATS_COL = db["salaar_threats"] if db is not None else None
SALAAR_MEMORY_COL = db["salaar_memory"] if db is not None else None
SALAAR_PEOPLE_COL = db["salaar_people"] if db is not None else None
SALAAR_ACTIONS_COL = db["salaar_actions"] if db is not None else None


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


# Generate a random unique ID.
def _uid():
    import uuid
    return str(uuid.uuid4())


def ensure_salaar_startup():
    """Idempotent indexes. Called from server startup."""
    if db is None:
        log.warning("SALAAR startup: db is None, skipping indexes")
        return
    for col_name, fields in [
        ("salaar_events", [("id", 1), ("org_id", 1)]),
        ("salaar_threats", [("id", 1), ("org_id", 1)]),
        ("salaar_memory", [("id", 1), ("org_id", 1)]),
        ("salaar_people", [("id", 1), ("org_id", 1)]),
        ("salaar_actions", [("id", 1), ("org_id", 1)]),
        ("salaar_behavior", [("id", 1), ("org_id", 1)]),
    ]:
        for field in fields:
            try:
                db[col_name].create_index([field], unique=field[0] == "id")
            except Exception as e:
                log.warning(f"SALAAR startup: index {col_name}.{field} failed: {e}")
    log.info("SALAAR startup: collections and indexes ready")


# ── Authority gradient (Constitution §6) ──
L0 = "L0"  # Observe only — read data, no actions
L1 = "L1"  # Execute reversible — auto, no notification
L2 = "L2"  # Execute + notify — auto, founder informed
L3 = "L3"  # Recommend — propose action, executive/founder approves
L4 = "L4"  # Escalate — propose, founder must approve
L5 = "L5"  # Restricted — founder only, irreversible/strategic

# Authority thresholds from trust rails
# Spend limits pulled from environment configuration.
APPROVAL_THRESHOLD_INR = int(__import__('os').environ.get("MCP_APPROVAL_THRESHOLD_INR", "5000"))
ORG_SPEND_CAP_INR = int(__import__('os').environ.get("ORG_MONTHLY_SPEND_CAP_INR", "25000"))


# ======================================================================
# THREAT DETECTION — Phase 2
# 169 lens patterns + business threat rules
# ======================================================================

# Threat categories mapped to lens triggers + severity
THREAT_RULES = {
    # --- People threats (powered by psychology lenses) ---
    "cofounder_conflict": {
        "lenses": ["berdee_psychopaths", "greene_human_nature", "kishimi_courage"],
        "triggers": ["cofounder", "co-founder", "partner disagree", "my cofounder wants",
                     "conflict with", "fighting over", "arguing about", "split equity"],
        "severity": "high",
        "action_level": L3,
        "diagnosis": "Cofounder relationship under strain. Detectable pattern: disagreements escalating, equity tension, role overlap.",
    },
    "key_person_risk": {
        "lenses": ["berdee_psychopaths", "greene_human_nature"],
        "triggers": ["only person who", "single point of failure", "if they leave", "key employee quit",
                     "cto leaving", "lead engineer", "bus factor"],
        "severity": "high",
        "action_level": L2,
        "diagnosis": "Single person owns critical knowledge/function. Bus factor = 1. Operational risk: high.",
    },
    "toxic_hire": {
        "lenses": ["berdee_psychopaths", "greene_human_nature", "kishimi_courage"],
        "triggers": ["gaslighting", "manipulating", "toxic", "making everyone", "culture problem",
                     "bad hire", "regret hiring", "everyone's afraid of", "walking on eggshells"],
        "severity": "high",
        "action_level": L4,
        "diagnosis": "A person in the organization is creating a toxic environment. Pattern: fear, silence, avoidance, complaints.",
    },
    "founder_isolation": {
        "lenses": ["kishimi_courage", "horowitz_struggle"],
        "triggers": ["alone in this", "no one to talk to", "can't tell anyone", "lonely founder",
                     "nobody understands", "carrying this alone", "isolation"],
        "severity": "medium",
        "action_level": L2,
        "diagnosis": "Founder showing signs of isolation — a leading indicator of burnout, bad decisions, and dropout.",
    },

    # --- Financial threats ---
    "cash_crisis": {
        "lenses": ["taleb_swan", "horowitz_struggle", "rumelt_kernel"],
        "triggers": ["runway", "cash", "burn rate", "out of money", "can't pay", "bankrupt",
                     "closing down", "no revenue", "losing money", "salaries", "not enough cash"],
        "severity": "critical",
        "action_level": L2,
        "diagnosis": "Cash position deteriorating. Pattern: burn accelerating, runway contracting, no plan B visible.",
    },
    "revenue_concentration": {
        "lenses": ["taleb_swan", "taleb_antifragile", "helmer_power"],
        "triggers": ["biggest client", "one customer", "anchor client", "depends on one", "single customer",
                     "80% revenue", "concentration risk", "if we lose"],
        "severity": "high",
        "action_level": L2,
        "diagnosis": "Revenue concentrated in too few customers. One loss = existential. Fragility detected.",
    },
    "pricing_undermining": {
        "lenses": ["sutherland_alchemy", "cialdini_influence", "helmer_power"],
        "triggers": ["underpricing", "discounting", "price war", "competitor cheaper", "losing on price",
                     "margin erosion", "can't charge more", "free tier eating"],
        "severity": "medium",
        "action_level": L3,
        "diagnosis": "Pricing power eroding. Discounting pattern detected. Value signaling broken.",
    },

    # --- Operational threats ---
    "execution_stalling": {
        "lenses": ["grove_leverage", "bungay_action", "heath_wrap"],
        "triggers": ["behind schedule", "delayed again", "not shipping", "missed deadline", "overdue",
                     "stuck in", "analysis paralysis", "waiting for", "blocked on"],
        "severity": "medium",
        "action_level": L2,
        "diagnosis": "Execution velocity dropping. Pattern: repeated delays, escalating blockers, no escalation path.",
    },
    "okr_stalling": {
        "lenses": ["grove_leverage", "doerr_okr"],
        "triggers": ["okr behind", "not hitting krs", "progress stalled", "quarter looking bad",
                     "won't make the quarter", "krs not moving"],
        "severity": "medium",
        "action_level": L1,
        "diagnosis": "OKR progress stalling. Auto-detected from execution data. Tasks not completing. Confidence dropping.",
    },
    "team_underload": {
        "lenses": ["grove_leverage", "coyle_culture"],
        "triggers": ["nothing to do", "bored", "not enough work", "team idle", "underutilized",
                     "waiting on", "no tasks assigned", "team member free"],
        "severity": "low",
        "action_level": L3,
        "diagnosis": "Team members underutilized. Resource waste detected. Assign or rebalance tasks.",
    },

    # --- Strategic threats ---
    "competitor_advance": {
        "lenses": ["christensen_jtbd", "helmer_power", "rumelt_kernel"],
        "triggers": ["competitor launched", "competitor raised", "losing to", "they're ahead",
                     "competitor has", "market share loss", "competitor copying", "they just shipped"],
        "severity": "high",
        "action_level": L3,
        "diagnosis": "Competitor making threatening moves. Pattern: they're shipping faster, raising more, gaining mindshare.",
    },
    "strategy_drift": {
        "lenses": ["rumelt_kernel", "bevelin_wisdom", "heath_wrap"],
        "triggers": ["pivot", "changing direction", "changed direction", "new strategy", "keep changing",
                     "can't commit", "chasing", "trying everything", "spread too thin", "pivoted",
                     "switched from", "changed from", "went from", "4 times", "3 times", "multiple times",
                     "back and forth", "different direction", "new direction", "another pivot",
                     "changing model", "business model again"],
        "severity": "high",
        "action_level": L3,
        "diagnosis": "Strategy changing too frequently. No single direction held long enough for results. Drift detected.",
    },
    "customer_churn_signal": {
        "lenses": ["christensen_jtbd", "fitzpatrick_momtest", "sharp_growth"],
        "triggers": ["customer leaving", "cancelling", "churning", "unhappy customer", "complaint",
                     "refund", "bad review", "nps dropping", "not renewing"],
        "severity": "high",
        "action_level": L2,
        "diagnosis": "Customer churn signal detected. Pattern: dissatisfaction, contract non-renewal, NPS decline.",
    },

    # --- Decision threats ---
    "decision_paralysis": {
        "lenses": ["heath_wrap", "kahneman_bias", "bevelin_wisdom", "kishimi_courage"],
        "triggers": ["can't decide", "stuck on", "not sure whether", "going back and forth",
                     "paralysis", "overthinking", "analysis", "what if I'm wrong"],
        "severity": "medium",
        "action_level": L2,
        "diagnosis": "Founder stuck in decision loop. Pattern: binary framing, no new information being gathered, fear of wrong choice.",
    },
    "sunk_cost_trap": {
        "lenses": ["kahneman_bias", "bevelin_wisdom", "taleb_swan"],
        "triggers": ["already invested", "sunk cost", "put so much into", "can't walk away",
                     "too far in", "already spent", "committed to this", "years into this",
                     "all this time", "wasted", "so much work", "can't stop now",
                     "months into", "invested so much", "gave up my", "quit my job for"],
        "severity": "medium",
        "action_level": L2,
        "diagnosis": "Sunk cost fallacy detected. Founder continuing because of past investment, not future return.",
    },
}


def match_threats(text: str, org_id: str) -> list[dict]:
    """Scan text against all threat rules. Returns list of detected threats."""
    if not text or not org_id:
        return []
    hay = text.lower()
    detected = []
    for threat_key, rule in THREAT_RULES.items():
        # Check triggers
        if not any(t in hay for t in rule["triggers"]):
            continue
        # Check existing memory — is this a repeat?
        prev = list(SALAAR_THREATS_COL.find(
            {"org_id": org_id, "threat_key": threat_key, "status": {"$ne": "resolved"}}
        ).sort("detected_at", -1).limit(3)) if SALAAR_THREATS_COL is not None else []
        repeat = len(prev) > 0
        detected.append({
            "threat_key": threat_key,
            "severity": rule["severity"],
            "action_level": rule["action_level"],
            "lenses": rule["lenses"],
            "diagnosis": rule["diagnosis"],
            "repeat": repeat,
            "previous_count": len(prev),
            "matched_text": text[:300],
        })
    return detected


def record_threat(org_id: str, threat_key: str, user_id: str, matched_text: str,
                  severity: str, lenses: list[str], diagnosis: str) -> Optional[str]:
    """Persist a detected threat. Returns threat_id or None."""
    if SALAAR_THREATS_COL is None:
        return None
    tid = _uid()
    SALAAR_THREATS_COL.insert_one({
        "id": tid, "org_id": org_id, "user_id": user_id, "threat_key": threat_key,
        "severity": severity, "lenses": lenses, "diagnosis": diagnosis,
        "matched_text": matched_text[:500], "status": "detected",
        "detected_at": _now(), "resolved_at": None, "resolution": None,
    })
    return tid


# ======================================================================
# PATTERN MEMORY — Phase 3
# Remembers threat→outcome pairs. If a pattern repeats, flags it.
# ======================================================================

def store_pattern_memory(org_id: str, pattern_key: str, evidence: dict) -> None:
    """Store an outcome for future pattern matching."""
    if SALAAR_MEMORY_COL is None:
        return
    SALAAR_MEMORY_COL.insert_one({
        "id": _uid(), "org_id": org_id, "pattern_key": pattern_key,
        "evidence": evidence, "stored_at": _now(),
    })


def recall_pattern(org_id: str, pattern_key: str, limit: int = 5) -> list[dict]:
    """Retrieve past occurrences of a pattern."""
    if SALAAR_MEMORY_COL is None:
        return []
    return list(SALAAR_MEMORY_COL.find(
        {"org_id": org_id, "pattern_key": pattern_key}
    ).sort("stored_at", -1).limit(limit))


def detect_repeat_pattern(org_id: str, pattern_key: str) -> Optional[str]:
    """If this pattern has occurred before with known outcome, return insight string."""
    past = recall_pattern(org_id, pattern_key, limit=3)
    if len(past) < 2:
        return None
    outcomes = [p.get("evidence", {}).get("outcome", "") for p in past]
    if len(set(outcomes)) == 1 and outcomes[0]:
        return f"Pattern '{pattern_key}' has occurred {len(past)} times with the same outcome: {outcomes[0]}"
    return None
