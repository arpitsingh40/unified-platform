"""Closed Decision→Action→Outcome Loop API — record outcomes and read the weekly loop review.
Owner-only access (the loop is a strategic founder tool).
"""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import orgs_col, members_col
from security import current_user
from loop import record_decision_outcome, generate_weekly_auto_review, loop_reports_col

log = logging.getLogger("loop_api")
router = APIRouter(prefix="/api/loop", tags=["loop"])


# Owner-only org resolution (mirrors system_router)
def _require_owner_org(user: dict) -> dict:
    """Get org where the caller is the owner. Returns org doc or 403."""
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can access the closed loop")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


# Request body for recording a decision outcome
class RecordOutcomeIn(BaseModel):
    decision_id: str = Field(min_length=1)
    prediction: Optional[str] = None
    actual: Optional[str] = None
    outcome: str = Field(default="pending")
    metrics_delta: Optional[dict] = None


# Record a decision outcome into the loop ledger
@router.post("/record")
def record(body: RecordOutcomeIn, user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    doc = record_decision_outcome(
        org["id"], body.decision_id, body.prediction, body.actual,
        body.outcome, metrics_delta=body.metrics_delta,
    )
    return {"ok": True, "org_id": org["id"], "record": doc}


# Generate this week's loop review plus the previous four reports
@router.get("/weekly-review")
def weekly_review(user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    report = generate_weekly_auto_review(org["id"])
    history = list(loop_reports_col.find({"org_id": org["id"]})
                   .sort("generated_at", -1).skip(1).limit(4)) if loop_reports_col is not None else []
    return {"org_id": org["id"], "report": report, "history": history}
