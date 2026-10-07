"""Governance — the single control plane for autonomous execution.

Phase 4 trust rails, centralized so every execution path funnels through one gate:
- Kill switch: instant global halt (env flag, DB sentinel, or process-level flag)
- Dry run: plan without invoking any tool
- Weekly spend caps: per-org caps with a global env default

execution_gate() is THE entry point — dispatcher, bridge, and task approval all call it.
"""
import os
import logging
from datetime import datetime, timezone, timedelta

from db import _col

log = logging.getLogger("governance")

# Collection handles
org_spend_col = _col("org_spend")
_governance_state_col = _col("governance_state")
_org_governance_col = _col("org_governance")

# Process-level kill switch — set_kill_switch(True) blocks executions immediately
_PROCESS_KILL_SWITCH = False

# Default weekly spend cap in INR when no env/org override exists
DEFAULT_WEEKLY_CAP = 10000


# Parse a truthy env flag ("1"/"true"/"yes"/"on")
def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


# Read a sentinel value from governance_state, safely (DB may be absent)
def _sentinel(key: str) -> bool:
    if _governance_state_col is None:
        return False
    doc = _governance_state_col.find_one({"key": key})
    return bool(doc and doc.get("value"))


# Start of the current week key ("YYYY-MM-DD", Monday-based)
def _week_key() -> str:
    try:
        from ontology.temporal import week_start
        return week_start().date().isoformat()
    except ImportError:
        now = datetime.now(timezone.utc)
        monday = now - timedelta(days=now.weekday())
        return monday.date().isoformat()


# Global kill switch: env flag, DB sentinel, or process flag (all checked each call)
def kill_switch_active() -> bool:
    """True if autonomous execution is globally halted right now."""
    if _PROCESS_KILL_SWITCH:
        return True
    if _env_flag("KILL_SWITCH"):
        return True
    return _sentinel("kill_switch")


# Set the kill switch: upsert sentinel + flip the process flag (immediate effect)
def set_kill_switch(active: bool):
    """Upsert the sentinel doc and set the process-level flag."""
    global _PROCESS_KILL_SWITCH
    _PROCESS_KILL_SWITCH = bool(active)
    if _governance_state_col is not None:
        _governance_state_col.update_one(
            {"key": "kill_switch"},
            {"$set": {"key": "kill_switch", "value": bool(active)}},
            upsert=True,
        )
    log.info(f"Governance kill switch set to {bool(active)}")


# Global dry-run mode: env flag or DB sentinel
def dry_run_enabled() -> bool:
    """True if execution should be planned but never performed."""
    if _env_flag("DRY_RUN"):
        return True
    return _sentinel("dry_run")


# Set dry-run mode via sentinel doc
def set_dry_run(active: bool):
    if _governance_state_col is not None:
        _governance_state_col.update_one(
            {"key": "dry_run"},
            {"$set": {"key": "dry_run", "value": bool(active)}},
            upsert=True,
        )
    log.info(f"Governance dry-run set to {bool(active)}")


# Weekly spend cap for an org: env default, org override wins
def get_weekly_cap(org_id) -> float:
    """Weekly cap in INR for the org (org override > env default)."""
    cap = float(os.environ.get("WEEKLY_SPEND_CAP_INR", DEFAULT_WEEKLY_CAP))
    if org_id and _org_governance_col is not None:
        doc = _org_governance_col.find_one({"org_id": org_id})
        if doc and doc.get("weekly_cap") is not None:
            cap = float(doc["weekly_cap"])
    return cap


# Persist an org-level weekly cap override
def set_weekly_cap(org_id, cap: float):
    if _org_governance_col is None:
        return
    _org_governance_col.update_one(
        {"org_id": org_id},
        {"$set": {"org_id": org_id, "weekly_cap": float(cap)}},
        upsert=True,
    )
    log.info(f"Governance weekly cap for org {org_id} set to {cap}")


# Record spend against the org's current week bucket
def record_spend(org_id, amount: float):
    """Upsert {org_id, week_start, total} in org_spend_col."""
    if org_spend_col is None or amount <= 0:
        return
    org_spend_col.update_one(
        {"org_id": org_id, "week_start": _week_key()},
        {"$inc": {"total": float(amount)},
         "$setOnInsert": {"org_id": org_id, "week_start": _week_key()}},
        upsert=True,
    )


# Total spend for the org in the current week
def spend_this_week(org_id) -> float:
    """Sum of the org's recorded spend for the current week."""
    if org_spend_col is None:
        return 0.0
    doc = org_spend_col.find_one({"org_id": org_id, "week_start": _week_key()})
    return float(doc.get("total", 0.0)) if doc else 0.0


# Core gate check: kill switch first, then weekly cap
def check_execution(org_id, amount: float = 0) -> tuple:
    """Return (allowed, reason) for an execution with projected spend `amount`."""
    if kill_switch_active():
        return False, "Kill switch is active — all autonomous execution is paused"
    cap = get_weekly_cap(org_id)
    spent = spend_this_week(org_id) if org_id else 0.0
    if spent + float(amount or 0) > cap:
        return False, (f"Weekly spend cap exceeded: ₹{spent:,.0f} already spent, "
                       f"₹{float(amount or 0):,.0f} more would cross the ₹{cap:,.0f} cap")
    return True, "ok"


# Single entry point for ALL execution paths — full state, never raises
def execution_gate(org_id, amount: float = 0) -> dict:
    """Return full governance state dict {allowed, reason, kill_switch, dry_run,
    spend_this_week, cap}. Raises nothing — callers decide what to do."""
    allowed, reason = check_execution(org_id, amount)
    return {
        "allowed": allowed,
        "reason": reason,
        "kill_switch": kill_switch_active(),
        "dry_run": dry_run_enabled(),
        "spend_this_week": spend_this_week(org_id) if org_id else 0.0,
        "cap": get_weekly_cap(org_id),
    }
