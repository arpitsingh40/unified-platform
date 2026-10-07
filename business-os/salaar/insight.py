"""SALAAR Insight Generator — Phase 7: Evidence, not conclusions.

SALAAR doesn't tell the founder "this person is toxic." It presents evidence:
"This person has missed 4 of 6 deadlines in 90 days. They disputed your decision
in 3 of 5 meetings. Their incentives diverge from yours on the contract renewal
in 2 weeks." The founder draws the conclusion.

SALAAR Brief = the one-page summary the founder sees when they open the app.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from db import db, orgs_col, tasks_col, members_col, threads_col

log = logging.getLogger("salaar.insight")

# SALAAR's MongoDB collections for threats, actions, people, memory.
SALAAR_THREATS_COL = db["salaar_threats"] if db is not None else None
SALAAR_ACTIONS_COL = db["salaar_actions"] if db is not None else None
SALAAR_PEOPLE_COL = db["salaar_people"] if db is not None else None
SALAAR_MEMORY_COL = db["salaar_memory"] if db is not None else None


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


def generate_salaar_brief(org_id: str, user_id: str) -> dict:
    """Generate the SALAAR Brief — what the founder sees when they open the app.
    
    Returns:
        {
            "threats_active": int,        # Number of active threats
            "threats_critical": int,      # Critical severity count
            "actions_pending": int,       # Actions awaiting founder approval
            "actions_auto_executed": int, # Actions SALAAR took silently (L1-L2)
            "people_of_concern": [...],   # People with red flags
            "top_alerts": [...],          # Top 3 things founder must know
            "last_scan_at": str,          # When SALAAR last ran
            "shadow_summary": str,        # One-sentence: what SALAAR handled while you were away
        }
    """
    now = _now()
    brief = {
        "threats_active": 0,
        "threats_critical": 0,
        "actions_pending": 0,
        "actions_auto_executed": 0,
        "people_of_concern": [],
        "top_alerts": [],
        "last_scan_at": now.isoformat(),
        "shadow_summary": "",
    }

    # Count active threats
    if SALAAR_THREATS_COL is not None:
        threats = list(SALAAR_THREATS_COL.find(
            {"org_id": org_id, "status": "detected"}
        ).sort("detected_at", -1))
        brief["threats_active"] = len(threats)
        brief["threats_critical"] = sum(1 for t in threats if t.get("severity") == "critical")

        # Top 3 alerts — critical first, then high, then most recent
        sorted_threats = sorted(threats, key=lambda t: (
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(t.get("severity"), 4),
            -t["detected_at"].timestamp() if isinstance(t["detected_at"], datetime) else 0
        ))
        for t in sorted_threats[:3]:
            brief["top_alerts"].append({
                "threat_key": t["threat_key"],
                "severity": t["severity"],
                "diagnosis": t.get("diagnosis", ""),
                "repeat": t.get("repeat_count", 0) > 0,
                "detected_at": t["detected_at"].isoformat() if isinstance(t["detected_at"], datetime) else str(t["detected_at"]),
            })

    # Count pending actions
    if SALAAR_ACTIONS_COL is not None:
        brief["actions_pending"] = SALAAR_ACTIONS_COL.count_documents(
            {"org_id": org_id, "status": "pending"}
        )
        brief["actions_auto_executed"] = SALAAR_ACTIONS_COL.count_documents(
            {"org_id": org_id, "status": "executed"}
        )

    # People of concern
    if SALAAR_PEOPLE_COL is not None:
        people = list(SALAAR_PEOPLE_COL.find(
            {"org_id": org_id, "red_flags": {"$ne": []}}
        ).sort("trust_score", 1).limit(5))
        for p in people:
            brief["people_of_concern"].append({
                "person_key": p["person_key"],
                "role": p.get("role", ""),
                "trust_score": p.get("trust_score", 50),
                "red_flags": p.get("red_flags", []),
                "mention_count": p.get("mention_count", 0),
                "negative_pct": round(
                    p.get("negative_mentions", 0) / max(p.get("mention_count", 1), 1) * 100, 1
                ),
            })

    # Active causal chains
    brief["active_chains"] = []
    try:
        chains_col = db["salaar_chains"] if db is not None else None
        if chains_col is not None:
            chains = list(chains_col.find(
                {"org_id": org_id, "type": "causal_chain", "status": "simulated"}
            ).sort("created_at", -1).limit(3))
            for c in chains:
                brief["active_chains"].append({
                    "chain_id": c.get("id", ""),
                    "chain_name": c.get("chain_name", ""),
                    "objective": c.get("objective", "")[:200],
                    "success_probability": c.get("success_probability"),
                    "total_steps": c.get("total_steps"),
                    "critical_link": c.get("critical_chain_link", ""),
                    "founder_only": c.get("founder_only_decision", ""),
                })
    except Exception:
        pass

    # Shadow summary: what SALAAR handled
    auto_count = brief["actions_auto_executed"]
    threat_count = brief["threats_active"]
    parts = []
    if auto_count > 0:
        parts.append(f"{auto_count} actions handled automatically")
    if threat_count > 0:
        parts.append(f"{threat_count} signals being tracked")
        if brief["threats_critical"] > 0:
            parts.append(f"{brief['threats_critical']} need your attention")
    if brief["actions_pending"] > 0:
        parts.append(f"{brief['actions_pending']} decisions waiting for you")
    brief["shadow_summary"] = " · ".join(parts) if parts else "All clear. No signals detected."

    return brief


def generate_people_insight(org_id: str, person_key: str) -> Optional[str]:
    """Generate an evidence-based insight about a specific person — for the founder to read.
    Never says 'this person is toxic.' Only presents evidence."""
    if SALAAR_PEOPLE_COL is None:
        return None
    person = SALAAR_PEOPLE_COL.find_one({"org_id": org_id, "person_key": person_key})
    if not person:
        return None

    lines = [f"Profile: {person_key}"]
    if person.get("role"):
        lines.append(f"Role: {person['role']}")
    lines.append(f"First observed: {person.get('first_seen_at')}")
    lines.append(f"Mentions: {person.get('mention_count', 0)} ({person.get('positive_mentions', 0)} positive, {person.get('negative_mentions', 0)} negative)")
    lines.append(f"Trust score: {person.get('trust_score', 50):.0f}/100")

    if person.get("red_flags"):
        lines.append(f"Detected patterns: {', '.join(person['red_flags'])}")

    if person.get("promises_made", 0) > 0:
        kept_pct = round(person.get("promises_kept", 0) / max(person["promises_made"], 1) * 100)
        lines.append(f"Promises kept: {person['promises_kept']}/{person['promises_made']} ({kept_pct}%)")

    return "\n".join(lines)


def generate_threat_resolution_insight(org_id: str, threat_key: str) -> Optional[str]:
    """Check if a threat has repeated with known outcomes."""
    if SALAAR_MEMORY_COL is None:
        return None
    from salaar.threats import recall_pattern, detect_repeat_pattern
    insight = detect_repeat_pattern(org_id, threat_key)
    if insight:
        return insight
    past = recall_pattern(org_id, threat_key, limit=3)
    if past:
        outcomes = [p.get("evidence", {}).get("outcome", "unknown") for p in past]
        return f"This pattern has appeared {len(past)} times before. Previous outcomes: {', '.join(outcomes)}"
    return None
