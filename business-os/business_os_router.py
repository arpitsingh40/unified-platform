"""Business OS API — autonomous operations dashboard + control plane."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from security import current_user
from db import members_col

# Business OS control plane routes
router = APIRouter(prefix="/api/business-os", tags=["business-os"])


# Resolve caller's active org id
def _get_org_id(user: dict) -> str:
    m = members_col.find_one({"user_id": user["id"], "status": "active"})
    if not m:
        raise HTTPException(403, "Not in an organization — create a workspace first")
    return m["org_id"]


# Restrict access to workspace owners
def _require_owner(user: dict) -> str:
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can manage Business OS")
    return m["org_id"]


# Live autonomous operations dashboard
@router.get("/status")
def get_os_status(user: dict = Depends(current_user)):
    """Live dashboard: what the Business OS is running autonomously."""
    org_id = _get_org_id(user)
    from business_os import os_status
    return os_status(org_id)


# Enumerate available business processes
@router.get("/processes")
def list_processes(user: dict = Depends(current_user)):
    """List available autonomous business processes."""
    from business_os import BUSINESS_PROCESSES
    return {
        "processes": {
            pid: {"label": p["label"], "schedule": p["schedule"],
                  "description": p["description"],
                  "agent_count": len(p["agent_chain"])}
            for pid, p in BUSINESS_PROCESSES.items()
        },
        "count": len(BUSINESS_PROCESSES),
    }


class RunProcessIn(BaseModel):
    process_id: str = Field(min_length=1, max_length=100)


class RunAllIn(BaseModel):
    process_ids: Optional[list[str]] = None


# Trigger full autonomous business cycle now
@router.post("/run")
def run_os_now(body: RunAllIn, user: dict = Depends(current_user)):
    """Owner: trigger a full autonomous business cycle now."""
    org_id = _require_owner(user)
    from business_os import business_cycle
    return business_cycle(org_id)


# Run a single business process now
@router.post("/processes/run")
def run_process(body: RunProcessIn, user: dict = Depends(current_user)):
    """Owner: run a specific business process now."""
    org_id = _require_owner(user)
    from business_os import run_business_process, BUSINESS_PROCESSES
    if body.process_id not in BUSINESS_PROCESSES:
        raise HTTPException(404, f"Unknown process: {body.process_id}")
    return run_business_process(org_id, body.process_id)


# Run all or selected business processes now
@router.post("/processes/run-all")
def run_all_processes(body: RunAllIn, user: dict = Depends(current_user)):
    """Owner: run all (or specified) business processes now."""
    org_id = _require_owner(user)
    from business_os import run_all_processes
    return run_all_processes(org_id, body.process_ids)


# Autonomous decision history
@router.get("/decisions")
def get_decisions(limit: int = 20, user: dict = Depends(current_user)):
    """History of autonomous decisions and their outcomes."""
    org_id = _get_org_id(user)
    from business_os import os_decisions
    return {"decisions": os_decisions(org_id, limit)}


# Connected tools status
@router.get("/tools")
def get_connected_tools(user: dict = Depends(current_user)):
    """List tools connected for autonomous execution."""
    org_id = _get_org_id(user)
    from business_os import _get_connected_tools
    tools = _get_connected_tools(org_id)
    return {
        "connected": tools,
        "count": len(tools),
        "can_execute": len(tools) > 0,
        "message": "Connect tools at /api/execution/connections to enable autonomous execution" if not tools
                   else f"{len(tools)} tools connected — Business OS is operational",
    }


# ── Founder Approval Inbox ──

class ApprovalAction(BaseModel):
    action: str = Field(min_length=1, max_length=20)  # approve | deny | edit
    note: Optional[str] = Field(default="", max_length=500)


# Pending approval inbox
@router.get("/approvals")
def get_approvals(user: dict = Depends(current_user)):
    """Founder's pending approval inbox."""
    org_id = _get_org_id(user)
    from business_os import get_pending_approvals, get_approval_summary
    return {
        "pending": get_pending_approvals(org_id),
        "summary": get_approval_summary(org_id),
    }


# Approve, deny, or edit an approval item
@router.post("/approvals/{approval_id}")
def handle_approval_endpoint(approval_id: str, body: ApprovalAction, user: dict = Depends(current_user)):
    """Approve, deny, or edit an agent's proposed action."""
    org_id = _get_org_id(user)
    from business_os import handle_approval
    result = handle_approval(approval_id, body.action, body.note or "")
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


# ── Outcome Verification ──

# Force business outcome verification
@router.post("/verify-outcome")
def verify_outcome_now(body: dict, user: dict = Depends(current_user)):
    """Force verification of a past execution outcome."""
    org_id = _get_org_id(user)
    from business_os import verify_business_outcome
    return verify_business_outcome(
        body.get("execution_id", ""),
        org_id,
        body.get("agent_type", ""),
        body.get("expected", ""),
        body.get("actual", ""),
    )


# ── Agent Quality Metrics ──

# Per-agent quality metrics
@router.get("/agent-quality")
def get_quality_metrics(user: dict = Depends(current_user)):
    """Per-agent quality: action rate, escalation rate, autonomy score."""
    org_id = _get_org_id(user)
    from agents import get_agent_quality
    return {"agents": get_agent_quality(org_id)}


# ── LLM Router Status ──

# Connected LLM providers and models
@router.get("/models")
def get_available_models(user: dict = Depends(current_user)):
    """List available models across all connected LLM providers."""
    from llm_router import available_models, _init_providers, _providers
    _init_providers()
    return {
        "providers": [p.name for p in _providers],
        "models": available_models(),
    }
