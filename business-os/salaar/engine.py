"""SALAAR Runtime Engine — the continuous scanner that runs underneath every interaction.

Runs on two cadences:
  - Realtime (every 5 min): scan recent messages/events for immediate threats
  - Deep (every 30 min): full scan — people profiles, business system health, pattern memory

The founder never sees SALAAR running. They see outcomes: alerts surfaced,
actions executed, people flagged, patterns detected.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import (
    db, orgs_col, members_col, threads_col, telemetry_col,
    tasks_col, decisions_col, plans_col,
)

log = logging.getLogger("salaar.engine")


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# PHASE 1: AWARENESS — scan all active orgs for signals
# ======================================================================

def scan_org(org_id: str):
    """Run a full SALAAR scan on one organization. Awareness → Threat Detection → Action.
    This is the core loop. Called every 5 min (realtime) and 30 min (deep)."""
    if not org_id or orgs_col is None:
        return {"scanned": False, "reason": "no org or db"}

    org = orgs_col.find_one({"id": org_id})
    if not org:
        return {"scanned": False, "reason": "org not found"}

    from salaar.threats import match_threats, record_threat
    from salaar.people import extract_people_from_text, get_or_create_person, scan_behavior
    from salaar.actions import decide_action_level, create_action
    from salaar.insight import generate_salaar_brief, generate_people_insight

    result = {
        "org_id": org_id,
        "org_name": org.get("name", ""),
        "scan_time": _now().isoformat(),
        "threats_detected": 0,
        "threats_recorded": 0,
        "actions_created": 0,
        "people_scanned": 0,
        "behaviors_detected": 0,
        "brief": None,
    }

    # ── Get the founder (owner)
    owner = members_col.find_one({"org_id": org_id, "role": "owner"})
    owner_uid = owner["user_id"] if owner else None
    if not owner_uid:
        return result

    # ── 1. Scan recent thread messages for threat signals
    recent_cutoff = _now() - timedelta(hours=6)
    recent_threads = list(threads_col.find({
        "user_id": owner_uid,
        "last_turn_at": {"$gte": recent_cutoff},
    })) if threads_col is not None else []

    all_text = ""
    for t in recent_threads:
        msgs = t.get("messages", [])
        for m in msgs[-5:]:  # Last 5 messages per thread
            if m.get("role") == "user":
                all_text += " " + (m.get("text", "") or "")

    # ── 2. Scan recent task descriptions and updates
    recent_tasks = list(tasks_col.find({
        "org_id": org_id,
        "updated_at": {"$gte": recent_cutoff.isoformat()},
    }).limit(10)) if tasks_col is not None else []

    for t in recent_tasks:
        all_text += " " + (t.get("title", "") or "")
        all_text += " " + (t.get("description", "") or "")

    # ── 3. Match threats against combined text
    threats = match_threats(all_text, org_id) if all_text.strip() else []
    result["threats_detected"] = len(threats)

    # ── 4. Record and act on each threat
    for threat in threats:
        tid = record_threat(
            org_id, threat["threat_key"], owner_uid,
            threat["matched_text"], threat["severity"],
            threat["lenses"], threat["diagnosis"],
        )
        if tid:
            result["threats_recorded"] += 1
            authority = decide_action_level(threat, org_id)
            aid = create_action(org_id, owner_uid, threat, authority)
            if aid:
                result["actions_created"] += 1

    # ── 5. Scan people from all text
    people_keys = extract_people_from_text(all_text)
    for pk in people_keys:
        person = get_or_create_person(org_id, pk, role=pk)
        behaviors = scan_behavior(all_text, person["id"], org_id)
        if behaviors:
            result["behaviors_detected"] += len(behaviors)
        result["people_scanned"] += 1

    # ── 6. Generate brief
    result["brief"] = generate_salaar_brief(org_id, owner_uid)

    log.info(
        f"SALAAR scan: {result['org_name']} — "
        f"{result['threats_detected']} threats, "
        f"{result['actions_created']} actions, "
        f"{result['behaviors_detected']} behaviors"
    )

    return result


# ======================================================================
# PHASE 2: DEEP SCAN — business system + pattern memory
# ======================================================================

def deep_scan_org(org_id: str):
    """Run a deep scan: business system health, pattern memory recall, lens re-weighting."""
    if not org_id:
        return {"scanned": False, "reason": "no org_id"}

    result = {"org_id": org_id, "system_health": None, "patterns_recalled": 0, "lenses_updated": False}

    # ── Check business system health from existing system model
    try:
        org = orgs_col.find_one({"id": org_id}) if orgs_col is not None else None
        if org and org.get("system_model"):
            sm = org["system_model"]
            functions = sm.get("functions") or {}
            health_scores = {f: s.get("health", 50) for f, s in functions.items() if isinstance(s, dict)}
            at_risk = [f for f, h in health_scores.items() if h < 40]
            result["system_health"] = {
                "functions": health_scores,
                "at_risk": at_risk,
                "at_risk_count": len(at_risk),
                "avg_health": round(sum(health_scores.values()) / max(len(health_scores), 1), 1),
            }

            # If functions are at risk, generate tasks
            if at_risk:
                try:
                    from execution.bridge import generate_tasks_for_at_risk_functions
                    generate_tasks_for_at_risk_functions(org_id)
                except Exception:
                    pass
    except Exception as e:
        log.warning(f"SALAAR deep scan: system model check failed for {org_id}: {e}")

    # ── Recall pattern memory for active threats
    try:
        from salaar.threats import detect_repeat_pattern, THREAT_RULES
        patterns_recalled = 0
        for threat_key in THREAT_RULES:
            insight = detect_repeat_pattern(org_id, threat_key)
            if insight:
                patterns_recalled += 1
        result["patterns_recalled"] = patterns_recalled
    except Exception as e:
        log.warning(f"SALAAR deep scan: pattern memory failed for {org_id}: {e}")
    
    # ── Auto-advance active causal chains ──
    try:
        from salaar.causal import auto_advance_chains
        chain_result = auto_advance_chains(org_id)
        result["chains_advanced"] = chain_result.get("advanced", 0)
        result["chains_fallback"] = chain_result.get("fallbacks_triggered", 0)
    except Exception as e:
        log.warning(f"SALAAR deep scan: chain auto-advance failed for {org_id}: {e}")

    return result


# ======================================================================
# CRON JOBS — wired into server scheduler
# ======================================================================

def salaar_realtime_scan():
    """Run every 5 minutes: scan all active orgs for immediate threats."""
    log.info("SALAAR: realtime scan starting")
    total_threats = 0
    total_actions = 0
    try:
        for org in orgs_col.find({}, {"_id": 0, "id": 1, "name": 1}):
            try:
                r = scan_org(org["id"])
                total_threats += r.get("threats_detected", 0)
                total_actions += r.get("actions_created", 0)
            except Exception as e:
                log.warning(f"SALAAR realtime: org {org.get('id')} failed: {e}")
    except Exception as e:
        log.exception(f"SALAAR realtime: global failure: {e}")
    log.info(f"SALAAR realtime scan complete — {total_threats} threats, {total_actions} actions")


def salaar_deep_scan():
    """Run every 30 minutes: full scan — people, patterns, system health."""
    log.info("SALAAR: deep scan starting")
    total_patterns = 0
    try:
        for org in orgs_col.find({}, {"_id": 0, "id": 1, "name": 1}):
            try:
                r = deep_scan_org(org["id"])
                total_patterns += r.get("patterns_recalled", 0)
            except Exception as e:
                log.warning(f"SALAAR deep: org {org.get('id')} failed: {e}")
    except Exception as e:
        log.exception(f"SALAAR deep: global failure: {e}")
    log.info(f"SALAAR deep scan complete — {total_patterns} patterns recalled")
