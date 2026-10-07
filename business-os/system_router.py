"""Business System API — the living model of the company exposed as a REST surface.
Owner-only access (these are strategic tools for the founder).
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import orgs_col, members_col
from security import current_user
from business_system import (
    init_system_model, persist_system_model, get_system_model,
    run_signal_scan, walk_root_cause, scan_opportunities,
)

log = logging.getLogger("business_system_api")
router = APIRouter(prefix="/api/system", tags=["business-system"])


# Request body for walking the root-cause tree.
class RootCauseIn(BaseModel):
    symptom: str = Field(description="The business function showing problems (e.g., 'sales', 'revenue', 'churn')")
    max_depth: int = Field(default=3, ge=1, le=5)


def _require_owner_org(user: dict) -> dict:
    """Get org where the caller is the owner. Returns org doc or 403."""
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can access the business system")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


@router.get("/model")
def get_model(user: dict = Depends(current_user)):
    """Get the current system model. Initializes one if missing."""
    org = _require_owner_org(user)
    model = get_system_model(org["id"])
    if not model:
        model = init_system_model(org)
        persist_system_model(org["id"], model)
    return {"org_id": org["id"], "model": model}


@router.post("/model/rebuild")
def rebuild_model(user: dict = Depends(current_user)):
    """Force-rebuild the system model from current org state."""
    org = _require_owner_org(user)
    model = init_system_model(org)
    persist_system_model(org["id"], model)
    return {"org_id": org["id"], "model": model, "rebuilt": True}


@router.get("/signals")
def get_signals(user: dict = Depends(current_user)):
    """Run the weekly signal scan. Returns the Founder Brief."""
    org = _require_owner_org(user)
    result = run_signal_scan(org["id"])
    return {"org_id": org["id"], **result}


@router.post("/root-cause")
def get_root_cause(body: RootCauseIn, user: dict = Depends(current_user)):
    """Walk the causal tree from a symptom function to find root causes."""
    org = _require_owner_org(user)
    result = walk_root_cause(org["id"], body.symptom, max_depth=body.max_depth)
    return {"org_id": org["id"], **result}


@router.get("/opportunities")
def get_opportunities(user: dict = Depends(current_user)):
    """Scan for untapped opportunities based on current business state."""
    org = _require_owner_org(user)
    result = scan_opportunities(org["id"])
    return {"org_id": org["id"], **result}
