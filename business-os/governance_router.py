"""Governance API — Phase 4 control plane surface (owner-only).

Owner routes for the kill switch, dry-run mode, and weekly spend caps.
All reads/writes go through governance.py so the process-level flags apply instantly.
"""
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from db import members_col, orgs_col
from security import current_user

log = logging.getLogger("governance.router")
router = APIRouter(prefix="/api/governance", tags=["governance"])


# Owner-only helper — same pattern as system_router
def _require_owner_org(user: dict) -> dict:
    """Get org where the caller is the owner. Returns org doc or 403."""
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can access governance controls")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


# Full governance status snapshot for an org
def _status(org_id) -> dict:
    from governance import kill_switch_active, dry_run_enabled, spend_this_week, get_weekly_cap
    ks = kill_switch_active()
    return {
        "kill_switch": ks,
        "dry_run": dry_run_enabled(),
        "spend_this_week": spend_this_week(org_id),
        "cap": get_weekly_cap(org_id),
        "locked": ks,
    }


# Request body for kill switch / dry-run toggles
class ActiveIn(BaseModel):
    active: bool


# Request body for weekly cap updates
class CapIn(BaseModel):
    weekly_cap: float


# Current governance state for the org
@router.get("/status")
def status(user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    return _status(org["id"])


# Set the global kill switch (blocks execution immediately)
@router.post("/kill-switch")
def kill_switch(body: ActiveIn, user: dict = Depends(current_user)):
    _require_owner_org(user)
    from governance import set_kill_switch
    set_kill_switch(body.active)
    return {"active": body.active}


# Toggle global dry-run mode
@router.post("/dry-run")
def dry_run(body: ActiveIn, user: dict = Depends(current_user)):
    _require_owner_org(user)
    from governance import set_dry_run
    set_dry_run(body.active)
    return {"active": body.active}


# Update this org's weekly spend cap
@router.post("/caps")
def caps(body: CapIn, user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    from governance import set_weekly_cap
    set_weekly_cap(org["id"], body.weekly_cap)
    return _status(org["id"])
