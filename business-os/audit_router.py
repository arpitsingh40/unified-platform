"""Record Room API — query and browse the unified audit trail."""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional

from security import current_user
from db import members_col

router = APIRouter(prefix="/api/audit", tags=["audit"])


# Resolve the user's active org ID
def _get_org_id(user: dict) -> str:
    m = members_col.find_one({"user_id": user["id"], "status": "active"})
    if not m:
        raise HTTPException(403, "Not in an organization — no audit trail available")
    return m["org_id"]


@router.get("")
def get_audit_log(
    event_type: Optional[str] = Query(default=None),
    actor_type: Optional[str] = Query(default=None),
    severity: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None),
    to_date: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(current_user),
):
    """Query the unified audit trail. Filter by event type, actor, severity, date range, or free-text search."""
    org_id = _get_org_id(user)
    from audit import query
    return query(org_id, event_type, actor_type, severity, from_date, to_date, search, limit, offset)


@router.get("/summary")
def get_audit_summary(hours: int = Query(default=24, ge=1, le=720), user: dict = Depends(current_user)):
    """Activity summary for the last N hours."""
    org_id = _get_org_id(user)
    from audit import summary
    return summary(org_id, hours)


@router.get("/types")
def get_event_types(user: dict = Depends(current_user)):
    """List all event types tracked in the audit trail."""
    from audit import EVENT_TYPES
    return {"types": EVENT_TYPES, "count": len(EVENT_TYPES)}
