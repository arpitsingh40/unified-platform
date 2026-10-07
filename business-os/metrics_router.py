"""Business Metrics API — Phase 1 business sensing REST surface.
Owner-only access: financial telemetry and alert feed for the founder."""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import members_col, orgs_col
from security import current_user
from metrics import compute_org_snapshot, ingest_metric, evaluate_metric_alerts, metric_alerts_col

log = logging.getLogger("metrics_api")
router = APIRouter(prefix="/api/metrics", tags=["metrics"])


# Request body for manual metric ingestion
class MetricIngestIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    value: float
    source: str = "manual"


def _require_owner_org(user: dict) -> dict:
    """Get org where the caller is the owner. Returns org doc or 403."""
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can access business metrics")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


# Business snapshot for the caller's org: cash, runway, MRR, churn, CAC + flags
@router.get("/snapshot")
def get_snapshot(user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    snap = compute_org_snapshot(org["id"])
    return {"org_id": org["id"], "snapshot": snap}


# Manually ingest a metric and re-evaluate alerts for the caller's org
@router.post("/ingest")
def ingest(body: MetricIngestIn, user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    metric_id = ingest_metric(org["id"], body.name.strip(), body.value, source=body.source)
    evaluate_metric_alerts(org["id"])
    return {"ok": True, "metric_id": metric_id}


# List the caller org's metric alerts, newest first (max 50)
@router.get("/alerts")
def list_alerts(user: dict = Depends(current_user)):
    org = _require_owner_org(user)
    alerts = list(metric_alerts_col.find({"org_id": org["id"]}).sort("created_at", -1).limit(50))
    return {"org_id": org["id"], "alerts": alerts, "count": len(alerts)}
