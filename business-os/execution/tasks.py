"""
Task Engine — generate, queue, approve, execute, verify, learn.

The mechanism of autonomy:
  Executive tasks born at L3 → Founder approval queue
  → Approve → TIE selects tool → Dispatch → Verify → Learn

Tasks persist in MongoDB (exec_tasks collection) — they survive restarts
and are org-scoped so one founder never sees another org's queue.
"""

import json
import logging
from typing import Optional
from llm_client import client, _extract_json, PRIMARY_MODEL
from db import exec_tasks_col

log = logging.getLogger("tasks")


# System prompt for first-week task generation
TASK_SYSTEM = """You are the Task Engine of SmartDecigen. Your job is to take an executive's mission, KPIs, and the company strategy, and generate the specific, concrete tasks they should execute in their first week.

RULES:
1. Each task must be specific — what exactly to do, not a vague goal
2. Each task must be completable in <3 days by one person
3. Each task must have a clear success criterion (how do we know it's done?)
4. The task should reference the capability needed (email, invoicing, etc.)
5. If the executive has no connected tools, suggest manual tasks that can later be automated
6. All tasks should be REVERSIBLE unless they involve real money or customer data

Return ONLY valid JSON, no markdown fences."""


def generate_tasks_for_executive(executive: dict, strategy: dict = None) -> list[dict]:
    """Generate first-week tasks for an executive. 1 LLM call per batch of executives.
    For efficiency, we call once with all executives and parse the result."""
    role = executive.get("role", "")
    mission = executive.get("mission", "")
    kpis = executive.get("kpis", [])
    dept = executive.get("department_id", "")

    kpi_lines = "\n".join(f"- {k.get('name', '')}: target {k.get('target', '')}" for k in kpis[:3])

    prompt = f"""EXECUTIVE: {role} ({dept})
MISSION: {mission}
KPIs:
{kpi_lines}
STRATEGY: {strategy.get('north_star', '') if strategy else 'Not set yet'}

Generate 3-4 FIRST-WEEK TASKS for this executive. Each task JSON:
{{"description": "Specific action (what, who, by when)", "capability": "email|invoicing|code_review|calendar|etc", "expected_outcome": "How we know it's done", "authority_required": "L3", "reversibility": "REVERSIBLE"}}

Return: {{"tasks": [task1, task2, task3]}}"""

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=800, system=TASK_SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
        return data.get("tasks", [])
    except Exception as e:
        log.error(f"Task generation failed for {role}: {e}")
        return [
            {"description": f"Define {role} top 3 priorities based on mission", "capability": "general",
             "expected_outcome": "Documented priorities with success criteria", "reversibility": "REVERSIBLE"},
            {"description": f"Review current workflows in {dept}", "capability": "general",
             "expected_outcome": "Identify top bottleneck", "reversibility": "REVERSIBLE"},
        ]


# Look up a task by id
def _find(task_id: str) -> Optional[dict]:
    if exec_tasks_col is None:
        return None
    return exec_tasks_col.find_one({"id": task_id}, {"_id": 0})


def enqueue_task(executive_id: str, task_data: dict, trace_id: str = None, org_id: str = None) -> str:
    """Add a task to the approval queue. Returns task_id."""
    tid = new_id("task_")
    task = {
        "id": tid,
        "org_id": org_id,
        "executive_id": executive_id,
        "description": task_data.get("description", ""),
        "capability": task_data.get("capability", "general"),
        "expected_outcome": task_data.get("expected_outcome", ""),
        "authority_required": task_data.get("authority_required", "L3"),
        "reversibility": task_data.get("reversibility", "REVERSIBLE"),
        # Optional concrete plan: [{tool, args, depends_on, description}].
        # Without it the task is honest manual work — we never invent tool calls.
        "plan": task_data.get("plan"),
        "estimated_cost_inr": int(task_data.get("estimated_cost_inr", 0) or 0),
        "status": "proposed",
        "trace_id": trace_id or new_id("trace_"),
        "created_at": utcnow().isoformat(),
        "approved_at": None,
        "executed_at": None,
        "verified_at": None,
        "result": None,
        "error": None,
        "verification": None,
    }
    if exec_tasks_col is not None:
        exec_tasks_col.insert_one(dict(task))

    # Audit trail
    try:
        from audit import record_task_event
        record_task_event(org_id, tid, "proposed", task_data.get("description", ""), executive_id)
    except Exception:
        pass

    return tid


def get_pending_tasks(executive_id: str = None, org_id: str = None) -> list[dict]:
    """Get all proposed tasks, optionally filtered by executive/org."""
    if exec_tasks_col is None:
        return []
    q = {"status": "proposed"}
    if executive_id:
        q["executive_id"] = executive_id
    if org_id:
        q["org_id"] = org_id
    return list(exec_tasks_col.find(q, {"_id": 0}).sort("created_at", 1))


def approve_task(task_id: str) -> dict:
    """Approve a task — triggers execution pipeline."""
    task = _find(task_id)
    if not task:
        return {"error": "task_not_found"}
    upd = {"status": "approved", "approved_at": utcnow().isoformat()}
    exec_tasks_col.update_one({"id": task_id}, {"$set": upd})
    task.update(upd)
    return task


def reject_task(task_id: str, reason: str = "") -> dict:
    """Reject a task with reason — feeds learning."""
    task = _find(task_id)
    if not task:
        return {"error": "task_not_found"}
    upd = {"status": "rejected", "result": f"Rejected: {reason}",
           "rejected_at": utcnow().isoformat()}
    exec_tasks_col.update_one({"id": task_id}, {"$set": upd})
    task.update(upd)
    return task


def mark_task_executed(task_id: str, result: str = "", error: str = "", status: str = None) -> dict:
    """Record execution result. status override allows 'manual' for tasks with no tool path."""
    task = _find(task_id)
    if not task:
        return {"error": "task_not_found"}
    upd = {
        "status": status or ("executed" if not error else "failed"),
        "executed_at": utcnow().isoformat(),
        "result": result[:2000] if result else (error[:500] if error else None),
        "error": error[:500] if error else None,
    }
    exec_tasks_col.update_one({"id": task_id}, {"$set": upd})
    task.update(upd)
    return task


def mark_task_verified(task_id: str, outcome: str, confidence: float, evidence_id: str = None) -> dict:
    """Record verification outcome. Only called with REAL verification results —
    never with invented confidence (Constitution §5: Evidence-First Learning)."""
    task = _find(task_id)
    if not task:
        return {"error": "task_not_found"}
    upd = {
        "status": "verified",
        "verified_at": utcnow().isoformat(),
        "verification": {"outcome": outcome, "confidence": confidence, "evidence_id": evidence_id},
    }
    exec_tasks_col.update_one({"id": task_id}, {"$set": upd})
    task.update(upd)
    return task


def set_task_fields(task_id: str, fields: dict) -> None:
    """Attach extra data to a task (e.g. recommended_tool, execution log)."""
    if exec_tasks_col is not None:
        exec_tasks_col.update_one({"id": task_id}, {"$set": fields})


# Fetch all tasks, optionally org-scoped
def get_all_tasks(org_id: str = None) -> list[dict]:
    if exec_tasks_col is None:
        return []
    q = {"org_id": org_id} if org_id else {}
    return list(exec_tasks_col.find(q, {"_id": 0}).sort("created_at", -1))


def task_summary(org_id: str = None) -> dict:
    """Dashboard summary."""
    all_tasks = get_all_tasks(org_id)
    counts = {}
    for t in all_tasks:
        counts[t.get("status", "unknown")] = counts.get(t.get("status", "unknown"), 0) + 1
    return {
        "total": len(all_tasks),
        "proposed": counts.get("proposed", 0),
        "approved": counts.get("approved", 0),
        "executed": counts.get("executed", 0),
        "manual": counts.get("manual", 0),
        "failed": counts.get("failed", 0),
        "verified": counts.get("verified", 0),
        "rejected": counts.get("rejected", 0),
    }


# ── Demo ──
if __name__ == "__main__":
    tid = enqueue_task("exec_1", {
        "description": "Send outreach email to 10 factory owners in Pune",
        "capability": "email", "expected_outcome": "3 replies expressing interest",
        "reversibility": "REVERSIBLE"
    }, org_id="org_demo")
    print(f"Task enqueued: {tid}")
    assert get_pending_tasks(org_id="org_demo"), "pending queue empty"
    approve_task(tid)
    mark_task_executed(tid, "Email sent to 10 contacts")
    mark_task_verified(tid, "SUCCESS", 0.9)
    s = task_summary(org_id="org_demo")
    assert s["verified"] == 1, s
    print(json.dumps(s, indent=2))
