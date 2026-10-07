"""SALAAR Action Engine — Phase 4: Execute/Recommend/Escalate/Block on L0-L5 gradient.

Every detected threat produces an action candidate. The action engine decides:
  L0 — Observe (record, do nothing visible)
  L1 — Execute reversible (auto, no notification)
  L2 — Execute + notify (auto, founder gets one-line summary)
  L3 — Recommend (prepare action package, executive approves)
  L4 — Escalate (prepare action package, founder must approve)
  L5 — Restricted (flag to founder, never execute autonomously)
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from db import db, orgs_col, tasks_col, members_col, users_col

log = logging.getLogger("salaar.actions")

SALAAR_ACTIONS_COL = db["salaar_actions"] if db is not None else None


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


# Generate a random unique ID.
def _uid():
    import uuid
    return str(uuid.uuid4())


# ── Action library — what SALAAR does for each threat ──
THREAT_ACTIONS = {
    "cofounder_conflict": {
        "level": "L3",
        "action_type": "mediation_prep",
        "title": "Cofounder conflict detected — prepare structured conversation",
        "description": "Cofounder tensions are visible in recent communications. The pattern suggests role overlap, equity tension, or strategic disagreement. SALAAR has prepared: a structured agenda for a cofounder offsite, the 3 critical questions each person should answer independently, and a decision framework for tiebreaking.",
        "tool": None,
        "reversible": True,
    },
    "key_person_risk": {
        "level": "L2",
        "action_type": "risk_mitigation",
        "title": "Key person risk detected — initiate knowledge transfer",
        "description": "A single person holds critical operational knowledge. SALAAR has: identified the bus-factor=1 functions, listed the specific knowledge only they hold, and created documentation tasks for each function to distribute risk.",
        "tool": None,
        "reversible": True,
    },
    "toxic_hire": {
        "level": "L4",
        "action_type": "people_decision",
        "title": "Toxic behavior pattern detected — evidence brief prepared",
        "description": "Multiple behavior patterns detected around one individual. SALAAR has compiled: the timeline of incidents, specific behavior patterns detected, team impact signals, and a structured termination or performance-plan framework. This is an L4 escalation — founder decision required.",
        "tool": None,
        "reversible": False,
    },
    "founder_isolation": {
        "level": "L2",
        "action_type": "support_signal",
        "title": "Founder isolation signal — peer connection suggested",
        "description": "You've signaled feeling alone in this. SALAAR notes: this is normal and survivable (Horowitz's 'The Struggle'). Action: identify one person you can share the real picture with this week. SALAAR can draft a message if helpful.",
        "tool": None,
        "reversible": True,
    },
    "cash_crisis": {
        "level": "L2",
        "action_type": "financial_alert",
        "title": "Cash position alert — runway analysis triggered",
        "description": "Financial distress signals detected. SALAAR has: flagged all non-essential spending for review, computed honest runway date from available data, identified the one dependency whose failure is fatal, and prepared cost-reduction options by function.",
        "tool": None,
        "reversible": True,
    },
    "revenue_concentration": {
        "level": "L2",
        "action_type": "risk_alert",
        "title": "Revenue concentration risk — diversification brief",
        "description": "Revenue concentrated in too few customers. SALAAR recommends: identify the next 3 highest-probability accounts, assess what would survive if the top account left, and set a concentration ceiling (e.g., no single customer > 30% of revenue).",
        "tool": None,
        "reversible": True,
    },
    "pricing_undermining": {
        "level": "L3",
        "action_type": "strategy_brief",
        "title": "Pricing power erosion — diagnostic prepared",
        "description": "Pricing signals suggest value capture is weakening. SALAAR recommends: audit your value signals (packaging, positioning, social proof), identify where discounting crept in, and test one price increase on a subset. Free tier may be cannibalizing paid conversion.",
        "tool": None,
        "reversible": True,
    },
    "execution_stalling": {
        "level": "L2",
        "action_type": "unblock",
        "title": "Execution stalling — blocker resolution triggered",
        "description": "Delivery velocity dropping. SALAAR has: identified the top 3 blocked items, assigned owners for each blocker, and set 48-hour resolution deadlines. Escalation path created for items that remain blocked.",
        "tool": None,
        "reversible": True,
    },
    "okr_stalling": {
        "level": "L1",
        "action_type": "auto_adjust",
        "title": "OKR stalling — auto-adjusted confidence and tasks",
        "description": "SALAAR detected stalling OKRs and auto-adjusted confidence scores. Recovery tasks generated for at-risk KRs. No founder action needed — this is L1 auto-execute.",
        "tool": None,
        "reversible": True,
    },
    "team_underload": {
        "level": "L3",
        "action_type": "resource_balance",
        "title": "Team underutilization — rebalance recommendation",
        "description": "Some team members have light loads while others are overloaded. SALAAR recommends reassigning tasks from overloaded to underloaded members. A draft task redistribution is ready for review.",
        "tool": None,
        "reversible": True,
    },
    "competitor_advance": {
        "level": "L3",
        "action_type": "competitive_intel",
        "title": "Competitor advance detected — strategic options brief",
        "description": "Competitor making threatening moves. SALAAR has: analyzed the specific threat (pricing? feature? funding?), identified your counter-position, and flagged whether this is wartime or peacetime. Response options prepared.",
        "tool": None,
        "reversible": True,
    },
    "strategy_drift": {
        "level": "L3",
        "action_type": "strategy_lock",
        "title": "Strategy drift detected — recommitment framework",
        "description": "Multiple strategy changes in recent weeks. SALAAR recommends: commit to the current direction for 90 days with written decision rules, define specific tripwires that would justify a change, and measure against the original hypothesis before pivoting.",
        "tool": None,
        "reversible": True,
    },
    "customer_churn_signal": {
        "level": "L2",
        "action_type": "retention_action",
        "title": "Customer churn signal — intervention triggered",
        "description": "Customer at risk of leaving. SALAAR recommends: personal outreach within 24 hours, understanding the root cause before offering concessions, and using the Mom Test to get real data (not politeness). Draft outreach message prepared.",
        "tool": None,
        "reversible": True,
    },
    "decision_paralysis": {
        "level": "L2",
        "action_type": "decision_unblock",
        "title": "Decision paralysis detected — WRAP framework applied",
        "description": "Founder stuck in decision loop. SALAAR has: widened the options from binary to 3+, reality-tested the assumptions, added distance (what would your best friend tell you to do?), and designed the smallest real-world test. One decision unblocked this turn.",
        "tool": None,
        "reversible": True,
    },
    "sunk_cost_trap": {
        "level": "L2",
        "action_type": "reframe",
        "title": "Sunk cost trap — zero-based reframe applied",
        "description": "Past investment driving current decisions. SALAAR has applied the zero-based reframe: would you start this today with zero history? The sunk cost is irrelevant to future returns. Separate the decision from the identity of having chosen the path.",
        "tool": None,
        "reversible": True,
    },
}


def decide_action_level(threat: dict, org_id: str) -> str:
    """Given a detected threat, determine the authority level for action."""
    threat_key = threat.get("threat_key", "")
    action_def = THREAT_ACTIONS.get(threat_key, {})
    default_level = action_def.get("level", "L3")
    severity = threat.get("severity", "medium")

    # Critical threats + irreversible actions → L4 or L5
    if severity == "critical" and not action_def.get("reversible", True):
        return "L5"
    if severity == "critical":
        return "L4"
    if threat.get("repeat") and threat.get("previous_count", 0) >= 3:
        # Repeating threat — escalate
        return min("L4", default_level) if default_level < "L4" else default_level

    return default_level


def create_action(org_id: str, user_id: str, threat: dict, authority: str) -> Optional[str]:
    """Create a SALAAR action in the database. Returns action_id or None."""
    if SALAAR_ACTIONS_COL is None:
        return None
    threat_key = threat.get("threat_key", "")
    action_def = THREAT_ACTIONS.get(threat_key, {})
    aid = _uid()
    SALAAR_ACTIONS_COL.insert_one({
        "id": aid, "org_id": org_id, "user_id": user_id,
        "threat_key": threat_key, "severity": threat.get("severity"),
        "authority_level": authority,
        "action_type": action_def.get("action_type", "advisory"),
        "title": action_def.get("title", f"SALAAR: {threat_key}"),
        "description": action_def.get("description", threat.get("diagnosis", "")),
        "reversible": action_def.get("reversible", True),
        "status": "pending" if authority in ("L3", "L4", "L5") else "executed",
        "created_at": _now(),
        "executed_at": _now() if authority in ("L1", "L2") else None,
        "approved_by": None,
        "approved_at": None,
    })

    # L1-L2: auto-execute and create a task
    if authority in ("L1", "L2") and tasks_col is not None:
        from db import members_col as mcol
        owner = mcol.find_one({"org_id": org_id, "role": "owner"})
        owner_uid = owner["user_id"] if owner else user_id
        tasks_col.insert_one({
            "id": _uid(), "org_id": org_id, "plan_id": "",
            "department_function": "general",
            "title": f"[SALAAR] {action_def.get('title', threat_key)}",
            "description": action_def.get("description", ""),
            "assigned_to": owner_uid,
            "assigned_to_name": "Founder",
            "status": "pending",
            "due_at": None,
            "week_start": None,
            "generated_week": _now().isocalendar()[1],
            "proof_files": [],
            "ai_review": {"status": "auto_generated", "notes": "SALAAR L1/L2 auto-action", "confidence": 0.85, "reviewed_at": _now().isoformat()},
            "stage": {"label": "not_started", "confidence": 1.0, "last_updated": _now().isoformat()},
            "escalation": {"dept_head_contacted": False, "dept_head_response": "", "founder_contacted": authority == "L2", "founder_response": "", "escalated_at": _now().isoformat() if authority == "L2" else None},
            "created_at": _now().isoformat(), "updated_at": _now().isoformat(), "completed_at": None,
        })
        SALAAR_ACTIONS_COL.update_one({"id": aid}, {"$set": {"status": "executed", "executed_at": _now()}})

    return aid
