"""
Tasks Router — founder task approval queue with TRUST RAILS.

Constitution wiring:
  §6  Authority Gradient  — L3 tasks blocked until founder approves
  §8  Explainability      — GET /{id}/brief = the Approval Brief (all outcomes, deterministic)
  §9  Reversibility       — declared per task, surfaced in the brief
  §10 Human Override      — kill switch pauses all autonomous execution
  §5  Evidence-First      — execution is verified for real or marked manual; never invented

GET  /api/tasks/pending        → org-scoped approval queue
GET  /api/tasks/{id}/brief     → Approval Brief: what runs, what it costs, what can go wrong
POST /api/tasks/{id}/approve   → permission + budget gates → execute → verify → learn
POST /api/tasks/{id}/reject    → reject with reason
POST /api/tasks/kill-switch    → pause/resume all autonomous execution (owner)
GET  /api/tasks/budget         → monthly autonomous-spend status (owner)
GET  /api/tasks                → all tasks (org-scoped)
GET  /api/tasks/summary        → dashboard counts (org-scoped)
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from security import current_user
from db import members_col, orgs_col, executives_col
from execution.tasks import (
    get_pending_tasks, approve_task, reject_task,
    get_all_tasks, task_summary, set_task_fields,
    mark_task_executed, mark_task_verified,
)
from execution.permissions import check_permission, requires_founder_review, _spending_from_args
from execution.verification import verify_action, learn_from_evidence

log = logging.getLogger("tasks.router")
router = APIRouter(prefix="/api/tasks")

# Monthly autonomous spend cap from env
MONTHLY_SPEND_CAP_INR = int(os.environ.get("ORG_MONTHLY_SPEND_CAP_INR", "25000"))


# Fetch active membership record for user
def _member(user: dict) -> Optional[dict]:
    return members_col.find_one({"user_id": user["id"], "status": "active"})


# Enforce founder-only access
def _require_owner(user: dict) -> dict:
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the founder can approve or reject executive tasks")
    return m


# Resolve user's org id from membership
def _org_scope(user: dict) -> Optional[str]:
    m = _member(user)
    return m["org_id"] if m else None


# Fetch task within org scope, 404 otherwise
def _own_task(task_id: str, org_id: str) -> dict:
    from execution.tasks import _find
    task = _find(task_id)
    if not task:
        raise HTTPException(404, "task_not_found")
    # Legacy tasks (org_id None) remain visible to any owner in that org context
    if task.get("org_id") and task["org_id"] != org_id:
        raise HTTPException(404, "task_not_found")
    return task


# Current month key for budget tracking
def _month_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


# Read org spend and pause state
def _budget_status(org_id: str) -> dict:
    org = orgs_col.find_one({"id": org_id}, {"_id": 0, "execution_budget": 1, "execution_paused": 1}) or {}
    b = org.get("execution_budget") or {}
    spent = b.get("spent_inr", 0) if b.get("month") == _month_key() else 0
    return {
        "month": _month_key(),
        "cap_inr": MONTHLY_SPEND_CAP_INR,
        "spent_inr": spent,
        "remaining_inr": max(0, MONTHLY_SPEND_CAP_INR - spent),
        "execution_paused": bool(org.get("execution_paused")),
    }


# Increment org monthly spend
def _record_spend(org_id: str, amount_inr: int):
    if amount_inr <= 0:
        return
    month = _month_key()
    org = orgs_col.find_one({"id": org_id}, {"execution_budget": 1}) or {}
    b = org.get("execution_budget") or {}
    if b.get("month") != month:
        orgs_col.update_one({"id": org_id}, {"$set": {"execution_budget": {"month": month, "spent_inr": amount_inr}}})
    else:
        orgs_col.update_one({"id": org_id}, {"$inc": {"execution_budget.spent_inr": amount_inr}})


def _planned_actions(task: dict) -> tuple[list[dict], Optional[dict]]:
    """Returns (concrete_actions, tool_recommendation).
    Concrete actions come only from an explicit task plan — we never invent tool calls.
    When there is no plan, TIE recommends the best tool for the capability (advisory)."""
    plan = task.get("plan")
    actions = plan.get("actions", []) if isinstance(plan, dict) else (plan if isinstance(plan, list) else [])
    actions = [a for a in actions if isinstance(a, dict) and a.get("tool")]

    recommendation = None
    if not actions:
        try:
            from execution.tie import select_best_tool
            from execution.mcp_client import linked_toolkits, mcp_enabled
            connected = {tk["toolkit"].lower(): True for tk in (linked_toolkits() if mcp_enabled() else [])}
            rec = select_best_tool(task.get("capability", "general"),
                                   {"connected_toolkits": connected,
                                    "authority_level": task.get("authority_required", "L3")})
            if rec.get("best"):
                recommendation = rec
        except Exception as e:
            log.warning(f"Tool recommendation failed: {e}")
    return actions, recommendation


# Collect risk flags for approval brief
def _risk_flags(task: dict, actions: list[dict]) -> list[str]:
    flags = []
    if task.get("reversibility") == "IRREVERSIBLE":
        flags.append("IRREVERSIBLE — cannot be undone once executed")
    if task.get("reversibility") == "PARTIALLY_REVERSIBLE":
        flags.append("Partially reversible — some effects may persist")
    spend = task.get("estimated_cost_inr", 0) or sum(_spending_from_args(a.get("args", {})) for a in actions)
    if spend > 0:
        flags.append(f"Real money involved: ~₹{spend}")
    for a in actions:
        if requires_founder_review(a.get("tool", ""), a.get("args", {}), spend):
            flags.append(f"Sensitive action: {a.get('tool')}")
        tool = a.get("tool", "").lower()
        if any(tool.startswith(p) for p in ("gmail", "linkedin", "twitter", "slack", "whatsapp")):
            flags.append(f"External communication: {a.get('tool')} — reaches real people")
    return sorted(set(flags))


# ────────────────────────────────────────────────────────── queue + views

# Founder approval queue for proposed tasks
@router.get("/pending")
def list_pending(executive_id: Optional[str] = None, user: dict = Depends(current_user)):
    """Founder's approval queue — all L3 tasks awaiting decision. Org-scoped."""
    org_id = _org_scope(user)
    if not org_id:
        return {"tasks": [], "count": 0}
    tasks = get_pending_tasks(executive_id, org_id=org_id)
    return {"tasks": tasks, "count": len(tasks)}


# Dashboard task counts with budget
@router.get("/summary")
def summary(user: dict = Depends(current_user)):
    org_id = _org_scope(user)
    out = task_summary(org_id)
    if org_id:
        out["budget"] = _budget_status(org_id)
    return out


# Monthly spend status for owner
@router.get("/budget")
def budget(user: dict = Depends(current_user)):
    m = _require_owner(user)
    return _budget_status(m["org_id"])


# Request body for kill switch toggle
class KillSwitchIn(BaseModel):
    paused: bool


# Founder kill switch for autonomous execution
@router.post("/kill-switch")
def kill_switch(body: KillSwitchIn, user: dict = Depends(current_user)):
    """Constitution §10 Human Override — founder pauses ALL autonomous execution instantly."""
    m = _require_owner(user)
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {"execution_paused": body.paused}})
    return {"execution_paused": body.paused}


# Deterministic approval brief for a task
@router.get("/{task_id}/brief")
def approval_brief(task_id: str, user: dict = Depends(current_user)):
    """The Approval Brief — everything the founder needs to decide, deterministic, zero LLM:
    what runs, who runs it, what it should achieve, what it costs, what can go wrong,
    whether it can be undone, and what exactly happens on approve."""
    m = _require_owner(user)
    task = _own_task(task_id, m["org_id"])

    ex = executives_col.find_one({"id": task.get("executive_id")}, {"_id": 0}) or {}
    actions, recommendation = _planned_actions(task)

    permission_checks = []
    for a in actions:
        pc = check_permission(a.get("tool", ""), a.get("args", {}),
                              caller_role="executive", executive_dna=ex, founder_approved=True)
        permission_checks.append({"tool": a.get("tool"), **pc})

    budget_now = _budget_status(m["org_id"])
    spend = task.get("estimated_cost_inr", 0) or sum(_spending_from_args(a.get("args", {})) for a in actions)

    if budget_now["execution_paused"]:
        on_approve = "Nothing — execution is paused by your kill switch. Resume it first."
    elif actions:
        on_approve = f"{len(actions)} tool action(s) execute immediately via connected tools, results are verified, evidence is stored."
    else:
        on_approve = "No concrete tool plan — task moves to the manual queue with a tool recommendation. Nothing executes autonomously."

    return {
        "task": task,
        "executive": {
            "id": ex.get("id"), "role": ex.get("role"), "mission": ex.get("mission"),
            "department": ex.get("department_id"),
            "lifecycle_status": (ex.get("lifecycle") or {}).get("status"),
            "spending_limit_inr": (ex.get("authority") or {}).get("spending_limit_inr", 0),
            "can_communicate_externally": (ex.get("authority") or {}).get("can_communicate_externally", False),
        },
        "planned_actions": actions,
        "tool_recommendation": recommendation,
        "permission_checks": permission_checks,
        "expected_outcome": task.get("expected_outcome"),
        "reversibility": task.get("reversibility"),
        "authority_required": task.get("authority_required"),
        "estimated_spend_inr": spend,
        "budget": budget_now,
        "risk_flags": _risk_flags(task, actions),
        "worst_case": ("Money spent with no result and the action cannot be undone"
                       if task.get("reversibility") == "IRREVERSIBLE" and spend > 0 else
                       "Action fails or produces no result; it is reversible and evidence will show exactly what happened"),
        "what_happens_if_approved": on_approve,
    }


# ────────────────────────────────────────────────────────── decisions

# Approve task, run gates then execute
@router.post("/{task_id}/approve")
def approve(task_id: str, user: dict = Depends(current_user)):
    """Approve a task. Runs the trust rails, then the real execution pipeline:
    permission gate → budget gate → dispatch → verify → learn. Honest at every step."""
    m = _require_owner(user)
    task = _own_task(task_id, m["org_id"])
    if task["status"] != "proposed":
        raise HTTPException(409, f"Task is already {task['status']}")

    budget_now = _budget_status(m["org_id"])
    if budget_now["execution_paused"]:
        raise HTTPException(423, "Execution is paused by the kill switch. Resume it in Mission Control first.")

    ex = executives_col.find_one({"id": task.get("executive_id")}, {"_id": 0}) or {}
    actions, recommendation = _planned_actions(task)

    # Gate 1 — permissions per action (founder approval satisfies the approval requirement,
    # but hard denials — archived executive, no rights — still block)
    for a in actions:
        pc = check_permission(a.get("tool", ""), a.get("args", {}),
                              caller_role="executive", executive_dna=ex, founder_approved=True)
        if not pc["allowed"]:
            raise HTTPException(403, f"Blocked: {a.get('tool')} — {pc['reason']}")

    # Gate 2 — budget cap on real spend
    spend = task.get("estimated_cost_inr", 0) or sum(_spending_from_args(a.get("args", {})) for a in actions)
    if spend > 0 and spend > budget_now["remaining_inr"]:
        raise HTTPException(402, f"Monthly autonomous-spend cap would be exceeded "
                                 f"(₹{spend} needed, ₹{budget_now['remaining_inr']} remaining). Raise the cap or reject.")

    # Governance gate: kill switch / weekly cap / dry-run consulted before dispatch
    from governance import execution_gate
    gov = execution_gate(m["org_id"], spend)
    if not gov["allowed"]:
        raise HTTPException(403, f"Governance blocked approval: {gov['reason']}")

    task = approve_task(task_id)

    # Execute — only a concrete plan executes; we never invent tool calls
    if actions:
        try:
            from execution.dispatcher import execute_plan, validate_plan
            plan = {"goal": task["description"], "actions": actions}
            issues = validate_plan(plan)
            if issues:
                raise ValueError(f"Invalid plan: {issues}")
            result = execute_plan(plan, department_function=ex.get("department_id", "general"),
                                   org_id=task.get("org_id"))
            set_task_fields(task_id, {"execution": result})

            done = result.get("summary", {}).get("done", 0)
            failed = result.get("summary", {}).get("failed", 0)
            first_result = next((r.get("result") for r in result.get("actions", []) if r and r.get("result")), "")
            first_error = next((r.get("error") for r in result.get("actions", []) if r and r.get("error")), "")

            task = mark_task_executed(task_id,
                                      result=first_result or f"{done}/{len(actions)} actions done",
                                      error=first_error if failed and not done else "")

            # Verify for real — Constitution §5
            ev = verify_action(
                tool_slug=actions[0].get("tool", "unknown"),
                capability=task.get("capability", "general"),
                expected_outcome=task.get("expected_outcome", ""),
                actual_result=(first_result or first_error or "no result returned"),
                trace_id=task.get("trace_id"),
                executive_id=task.get("executive_id"),
                org_id=m["org_id"],
            )
            task = mark_task_verified(task_id, ev.outcome.value, ev.confidence, getattr(ev, "id", None))
            learn_from_evidence(ev, task.get("capability", ""), org_id=m["org_id"])
            if done and spend > 0:
                _record_spend(m["org_id"], spend)
        except Exception as e:
            log.warning(f"Task execution failed: {e}")
            task = mark_task_executed(task_id, error=str(e)[:300])
    else:
        # Honest manual path: no tools connected / no concrete plan → nothing executes,
        # nothing is fake-verified. The founder gets a recommendation instead.
        note = "Manual execution required — no concrete tool plan"
        if recommendation and recommendation.get("best"):
            note += f". Recommended tool: {recommendation['best']['tool_slug']}"
            set_task_fields(task_id, {"recommended_tool": recommendation["best"]})
        task = mark_task_executed(task_id, result=note, status="manual")

    return {"task": task, "status": task["status"]}


# Request body for task rejection
class RejectIn(BaseModel):
    reason: str = ""


# Reject a proposed task
@router.post("/{task_id}/reject")
def reject(task_id: str, body: RejectIn, user: dict = Depends(current_user)):
    m = _require_owner(user)
    _own_task(task_id, m["org_id"])   # 404s if missing/foreign — the only not-found gate needed
    task = reject_task(task_id, body.reason)
    return {"task": task, "status": "rejected"}


# List all org tasks with filters
@router.get("")
def list_all(status: Optional[str] = None, executive_id: Optional[str] = None,
             user: dict = Depends(current_user)):
    org_id = _org_scope(user)
    if not org_id:
        return {"tasks": [], "count": 0}
    tasks = get_all_tasks(org_id)
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    if executive_id:
        tasks = [t for t in tasks if t["executive_id"] == executive_id]
    return {"tasks": tasks[:50], "count": len(tasks)}
