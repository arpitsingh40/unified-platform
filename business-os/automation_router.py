"""Automation API — owner-only triggers and status for the three Phase-3 automation loops.
Routes: POST /run/{loop_name}, GET /status, GET /runs.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends

from db import orgs_col, members_col
from security import current_user
from ontology.models import utcnow
import automation_loops

log = logging.getLogger("automation_api")
router = APIRouter(prefix="/api/automation", tags=["automation"])

# Supported loop names
LOOPS = ("cash", "customer", "team", "all")


# Owner-org gate (same pattern as system_router.py)
def _require_owner_org(user: dict) -> dict:
    """Get org where the caller is the owner. Returns org doc or 403."""
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can access automation")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


@router.post("/run/{loop_name}")
def run_loop(loop_name: str, user: dict = Depends(current_user)):
    """Execute one automation loop now: cash, customer, team, or all."""
    org = _require_owner_org(user)
    if loop_name not in LOOPS:
        raise HTTPException(404, f"Unknown loop '{loop_name}'. Use one of: {', '.join(LOOPS)}")
    started = utcnow().isoformat()
    fn = automation_loops.run_all_loops if loop_name == "all" \
        else getattr(automation_loops, f"run_{loop_name}_loop")
    result = fn(org["id"])
    return {
        "loop": loop_name,
        "org_id": org["id"],
        "started": started,
        "dry_run": automation_loops.dry_run_enabled(),
        "steps": result.get("steps", []),
        **{k: v for k, v in result.items() if k not in ("loop", "steps")},
    }


@router.get("/status")
def automation_status(user: dict = Depends(current_user)):
    """Governance state + last runs + per-loop step summaries for the org."""
    org = _require_owner_org(user)
    last_runs = automation_loops.latest_runs(org["id"], limit=10)
    loops = {}
    for name in ("cash", "customer", "team"):
        latest = next((r for r in last_runs if r.get("loop") == name), None)
        loops[name] = automation_loops.step_summary(latest)
    return {
        "governance": {
            "kill_switch": automation_loops.kill_switch_active(),
            "dry_run": automation_loops.dry_run_enabled(),
        },
        "last_runs": last_runs,
        "loops": loops,
    }


@router.get("/runs")
def automation_runs(user: dict = Depends(current_user)):
    """Latest 50 automation run documents for the org."""
    org = _require_owner_org(user)
    return {"org_id": org["id"], "runs": automation_loops.latest_runs(org["id"], limit=50)}
