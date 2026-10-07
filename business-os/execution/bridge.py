"""Execution Bridge — connects the system model to the execution runtime.

Wire 1: at-risk functions → task generation
Wire 2: engine actions → execution routing
Wire 3: journey plans → executable tasks
Wire 4: budget enforcement + execution triggers

The execution runtime is infrastructure. This module makes it USEFUL.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from db import orgs_col, members_col
from execution.tasks import enqueue_task, get_pending_tasks, task_summary
from execution.dispatcher import execute_plan as dispatch_plan, validate_plan

log = logging.getLogger("execution.bridge")


# Current UTC timestamp helper
def utcnow():
    return datetime.now(timezone.utc)


# ======================================================================
# Wire 1: System health → task generation
# ======================================================================

def generate_tasks_for_at_risk_functions(org_id: str, dry_run: bool = False) -> list[str]:
    """Scan the system model, find at-risk functions, generate executable tasks.
    Auto-attaches workflow-based execution plans. Auto-approves diagnostic tasks (L2-L3).
    Returns list of task IDs generated."""
    org = orgs_col.find_one({"id": org_id})
    if not org:
        return []

    sm = org.get("system_model") or {}
    functions = sm.get("functions") or {}
    at_risk = {f: s for f, s in functions.items() if s.get("status") == "at_risk"}

    if not at_risk:
        return []

    # Load workflow templates for matching
    try:
        from execution.workflows import WORKFLOWS, workflow_to_execution_plan
    except ImportError:
        WORKFLOWS = {}
        workflow_to_execution_plan = lambda w: None

    from business_system import FUNCTION_LABELS, _failure_modes_for
    from execution.tasks import approve_task

    task_ids = []

    for func, state in sorted(at_risk.items(), key=lambda x: x[1].get("health", 50)):
        label = FUNCTION_LABELS.get(func, func)
        health = state.get("health", 50)
        failures = _failure_modes_for(func)[:3]
        if not failures:
            continue

        # Find a relevant workflow for this function
        func_workflows = WORKFLOWS.get(func, [])
        best_workflow = func_workflows[0] if func_workflows else None
        plan = workflow_to_execution_plan(best_workflow) if best_workflow else None

        # Task 1: Diagnostic
        task_data = {
            "description": f"[AUTO] {label} at {health}/100 — investigate: {'; '.join(failures[:2])}",
            "capability": "diagnostic",
            "expected_outcome": f"Root cause of {label} decline identified with actionable fix plan",
            "authority_required": "L2",
            "reversibility": "REVERSIBLE",
            "estimated_cost_inr": 0,
            "plan": plan,
        }
        if not dry_run:
            tid = enqueue_task("system", task_data, org_id=org_id,
                              trace_id=f"sys_scan_{func}")
            # Auto-approve low-risk diagnostic tasks
            approve_task(tid)
            task_ids.append(tid)

        # Task 2: Execute recommended workflow if one matches
        if best_workflow and best_workflow["risk"] in ("L2", "L3"):
            task_data2 = {
                "description": f"[AUTO] Execute: {best_workflow['description']} (for {label})",
                "capability": func,
                "expected_outcome": best_workflow["expected_outcome"],
                "authority_required": best_workflow["risk"],
                "reversibility": "REVERSIBLE",
                "estimated_cost_inr": 0,
                "plan": plan,
            }
            if not dry_run:
                tid2 = enqueue_task("system", task_data2, org_id=org_id,
                                   trace_id=f"sys_scan_{func}_exec")
                # Auto-approve: L2-L3 tasks with zero cost are safe
                if best_workflow["risk"] not in ("L4", "L5"):
                    approve_task(tid2)
                task_ids.append(tid2)

    if task_ids:
        log.info(f"Wire 1+: {len(task_ids)} tasks (auto-approved) for {len(at_risk)} at-risk functions in org {org_id}")
    return task_ids


# ======================================================================
# Wire 2: Engine actions → execution routing
# ======================================================================

def enqueue_engine_action(org_id: str, action: dict, user_id: str = None) -> Optional[str]:
    """Take an action the engine/LLM identified and queue it for execution.
    action: {description, capability, tool, args, expected_outcome, reversibility}"""
    description = action.get("description", action.get("tool", "unnamed action"))
    if not description or len(description) < 5:
        return None

    plan = None
    if action.get("tool"):
        plan = [{
            "tool": action["tool"],
            "args": action.get("args", {}),
            "depends_on": [],
            "description": description,
        }]

    task_data = {
        "description": description[:200],
        "capability": action.get("capability", "general"),
        "expected_outcome": action.get("expected_outcome", "Action completed"),
        "authority_required": action.get("authority_required", "L3"),
        "reversibility": action.get("reversibility", "REVERSIBLE"),
        "estimated_cost_inr": int(action.get("estimated_cost_inr", 0) or 0),
        "plan": plan,
    }

    tid = enqueue_task(user_id or "engine", task_data, org_id=org_id,
                      trace_id=f"engine_{utcnow().strftime('%Y%m%d%H%M%S')}")
    if plan:
        log.info(f"Wire 2: enqueued engine action '{description[:80]}' with tool plan, task={tid}")
    else:
        log.info(f"Wire 2: enqueued manual engine action '{description[:80]}', task={tid}")
    return tid


# ======================================================================
# Wire 3: Journey operating plan → executable tasks
# ======================================================================

def generate_tasks_from_operating_plan(org_id: str, plan: dict, user_id: str = None) -> list[str]:
    """Convert a journey Phase 3 operating plan into executable tasks."""
    if not plan:
        return []

    task_ids = []

    # Daily rhythms → tasks
    for item in plan.get("daily", [])[:4]:
        tid = enqueue_task(user_id or "journey", {
            "description": f"[Daily] {item[:200]}",
            "capability": "operations",
            "expected_outcome": "Daily rhythm established",
            "authority_required": "L3",
            "reversibility": "REVERSIBLE",
        }, org_id=org_id, trace_id="journey_ops_daily")
        task_ids.append(tid)

    # Weekly rhythms → tasks
    for item in plan.get("weekly", [])[:3]:
        tid = enqueue_task(user_id or "journey", {
            "description": f"[Weekly] {item[:200]}",
            "capability": "operations",
            "expected_outcome": "Weekly cadence running",
            "authority_required": "L3",
            "reversibility": "REVERSIBLE",
        }, org_id=org_id, trace_id="journey_ops_weekly")
        task_ids.append(tid)

    # Responsibilities → tasks
    for resp in plan.get("responsibilities", [])[:5]:
        who = resp.get("who", "team member")
        what = resp.get("what", "")
        if what:
            tid = enqueue_task(user_id or "journey", {
                "description": f"[Owner: {who}] {what[:200]}",
                "capability": "general",
                "expected_outcome": f"Responsibility delivered by {who}",
                "authority_required": "L3",
                "reversibility": "REVERSIBLE",
            }, org_id=org_id, trace_id="journey_resp")
            task_ids.append(tid)

    if task_ids:
        log.info(f"Wire 3: generated {len(task_ids)} tasks from operating plan for org {org_id}")
    return task_ids


# ======================================================================
# Wire 4: Execution triggers + budget enforcement
# ======================================================================

def execute_approved_tasks(org_id: str = None, max_tasks: int = 10) -> dict:
    """Execute all approved-but-unexecuted tasks. Called by cron or API."""
    from execution.tasks import get_all_tasks, mark_task_executed, set_task_fields

    tasks = get_all_tasks(org_id)
    approved = [t for t in tasks if t.get("status") == "approved"]
    if not approved:
        return {"executed": 0, "message": "No approved tasks to execute"}

    executed = 0
    results = []
    for task in approved[:max_tasks]:
        plan = task.get("plan")
        if not plan:
            # Task has no tool plan — mark as manual
            mark_task_executed(task["id"], status="manual",
                              result="No tool plan — requires manual execution")
            continue

        # Validate plan
        issues = validate_plan({"goal": task.get("description", ""), "actions": plan})
        if issues:
            mark_task_executed(task["id"], error=f"Plan validation failed: {'; '.join(issues)}",
                              status="failed")
            continue

        # Budget enforcement
        cost = task.get("estimated_cost_inr", 0)
        if cost > 0:
            budget = _get_budget_status(task.get("org_id"))
            spent = budget.get("spent_this_month", 0)
            cap = budget.get("monthly_cap", 100000)
            if spent + cost > cap:
                log.warning(f"Wire 4 BUDGET: task {task['id']} costs {cost}INR, monthly spent={spent}, cap={cap} — blocked")
                continue

        # Governance gate: kill switch / weekly cap / dry-run — skip with reason when blocked
        try:
            from governance import execution_gate
            gate = execution_gate(task.get("org_id"), cost)
            if not gate["allowed"]:
                mark_task_executed(task["id"], status="skipped",
                                   error=f"Blocked by governance: {gate['reason']}")
                results.append({"task_id": task["id"], "status": "skipped",
                                "reason": gate["reason"]})
                continue
        except Exception:
            pass

        # Dispatch
        result = dispatch_plan({"goal": task.get("description", ""), "actions": plan}, "general")
        status = "executed" if result["summary"]["failed"] == 0 else (
            "failed" if result["summary"]["done"] == 0 else "executed")

        mark_task_executed(task["id"],
                          result=f"Executed: {result['summary']['done']}/{result['summary']['total']} done",
                          error=str(result["summary"]) if result["summary"]["failed"] > 0 else "",
                          status=status)
        set_task_fields(task["id"], {"execution_log": result})
        executed += 1
        results.append({"task_id": task["id"], "status": status, "summary": result["summary"]})

    log.info(f"Wire 4: executed {executed}/{len(approved)} approved tasks")
    return {"executed": executed, "results": results}


# Read org monthly execution budget state
def _get_budget_status(org_id: str) -> dict:
    """Read the org's monthly execution budget from the org doc."""
    org = orgs_col.find_one({"id": org_id}, {"_id": 0, "execution_budget": 1})
    budget = org.get("execution_budget") if org else {}
    return {
        "monthly_cap": int(budget.get("monthly_cap", 100000)),
        "spent_this_month": int(budget.get("spent_this_month", 0)),
        "kill_switch": bool(budget.get("kill_switch", False)),
    }


# Hard-check spend allowance against monthly cap
def enforce_budget(org_id: str, cost: int) -> bool:
    """Hard-check: can we spend this amount? Returns True if allowed."""
    budget = _get_budget_status(org_id)
    if budget["kill_switch"]:
        return False
    return (budget["spent_this_month"] + cost) <= budget["monthly_cap"]


# Record spend against the monthly budget
def record_spend(org_id: str, cost: int):
    """Record a spend against the monthly budget."""
    # Governance: centralize weekly spend tracking for caps (advisory — never fails the caller)
    try:
        from governance import record_spend as gov_record_spend
        gov_record_spend(org_id, cost)
    except Exception:
        pass
    orgs_col.update_one(
        {"id": org_id},
        {"$inc": {"execution_budget.spent_this_month": cost}},
    )


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    print("OK — execution bridge module ready (run from app context for full self-check)")
