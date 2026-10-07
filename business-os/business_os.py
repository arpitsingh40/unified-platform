"""Autonomous Business OS — the execution layer that runs your company.

Where agents.py decided "what to do" and bridge.py queued it for approval,
this module CLOSES THE LOOP: agents autonomously execute through connected
Composio tools, verify outcomes, learn, and adapt — on schedule.

Architecture:
  System Scan → Agent detects issue → Builds execution plan from workflows
  → Dispatches through MCP/Composio tools → Verifies outcome → Learns → Adapts
  → Founder sees a live dashboard of autonomous operations

No manual approval for L2-L3 actions. Founder sets the guardrails once.
"""
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db as _db, orgs_col, members_col
from llm_client import client as llm_client, _extract_json, PRIMARY_MODEL

log = logging.getLogger("business_os")

# Collections for OS run history and decision outcomes
OS_RUNS_COL = _db.os_runs if _db is not None else None
OS_DECISIONS_COL = _db.os_decisions if _db is not None else None

if OS_RUNS_COL is not None:
    OS_RUNS_COL.create_index("id", unique=True)
    OS_RUNS_COL.create_index([("org_id", 1), ("created_at", -1)])
if OS_DECISIONS_COL is not None:
    OS_DECISIONS_COL.create_index("id", unique=True)
    OS_DECISIONS_COL.create_index([("org_id", 1), ("status", 1)])


# Timezone-aware current UTC timestamp
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# Autonomous execution: agent decision → tool execution → verification
# ======================================================================

def _get_connected_tools(org_id: str) -> list[str]:
    """List toolkits connected for this org via Composio."""
    try:
        from execution.mcp_client import linked_toolkits, mcp_enabled
        if not mcp_enabled():
            return []
        toolkits = linked_toolkits()
        return [t["toolkit"] for t in toolkits]
    except Exception:
        return []


def _get_function_tools(function: str) -> list[str]:
    """Map business function to required toolkits."""
    from execution.connections import FUNCTION_TO_TOOLKITS
    return FUNCTION_TO_TOOLKITS.get(function, ["notion", "gmail", "slack"])


def _build_execution_plan(agent_type: str, decision: dict, org_id: str) -> Optional[dict]:
    """Convert an agent decision into an executable tool plan.
    Uses workflow templates when available, otherwise constructs from decision context."""
    connected = _get_connected_tools(org_id)
    if not connected:
        return None

    action = decision.get("action", "NOTHING")
    if action == "NOTHING":
        return None

    # Map agent types to functions they own
    agent_function_map = {
        "sales_agent": "sales",
        "marketing_agent": "marketing",
        "customer_agent": "customer_success",
        "ops_agent": "operations",
        "finance_agent": "finance",
        "tech_agent": "technology",
        "brand_agent": "brand",
        "growth_agent": "growth",
        "strategy_agent": "strategy",
        "product_agent": "product",
        "hr_agent": "hr",
        "system_agent": "operations",
    }
    func = agent_function_map.get(agent_type, "operations")
    needed_tools = _get_function_tools(func)
    available = [t for t in needed_tools if any(t in c for c in connected)]

    actions = []

    # Build tool calls based on agent decision type
    if action in ("FOLLOW_UP_LEADS", "INTERVENE", "ALERT") and any("gmail" in c for c in connected):
        summary = decision.get("summary", "")[:200]
        rec = decision.get("recommendation", "")[:200]
        actions.append({
            "tool": "GMAIL_SEND_EMAIL",
            "args": {
                "to": "{contact_email}",
                "subject": f"[{agent_type.replace('_agent','').upper()}] Action required: {summary[:80]}",
                "body": f"Hi,\n\n{summary}\n\nRecommended action: {rec}\n\nBest,\nSmartDecigen Business OS",
            },
            "depends_on": [],
            "description": f"Send alert email for: {summary[:80]}",
        })

    if action in ("CREATE_TICKET", "DRAFT_MEMO", "GENERATE_TASKS") and any("notion" in c for c in connected):
        summary = decision.get("summary", "")[:200]
        rec = decision.get("recommendation", "")[:200]
        actions.append({
            "tool": "NOTION_CREATE_PAGE",
            "args": {
                "title": f"[{agent_type.replace('_agent','').upper()}] {summary[:80]}",
                "content": f"**Issue:** {summary}\n\n**Recommendation:** {rec}\n\n**Detected by:** SmartDecigen Business OS\n**Time:** {_now().isoformat()}",
            },
            "depends_on": [],
            "description": f"Document issue in Notion: {summary[:80]}",
        })

    if actions and any("slack" in c for c in connected):
        summary = decision.get("summary", "")[:150]
        actions.append({
            "tool": "SLACK_SEND_MESSAGE",
            "args": {
                "channel": "#general",
                "text": f"[{agent_type.replace('_agent','').upper()}] {summary} — Action taken by Business OS",
            },
            "depends_on": [],
            "description": "Notify team via Slack",
        })

    if not actions:
        return None

    return {
        "goal": f"[Auto] {decision.get('summary', agent_type)}",
        "actions": actions,
    }


def execute_agent_decision(org_id: str, agent_type: str, decision: dict) -> dict:
    """Take an agent's decision and execute it through connected tools.
    Returns {executed, results, verification}."""
    plan = _build_execution_plan(agent_type, decision, org_id)
    if not plan:
        return {
            "executed": False,
            "reason": "no_connected_tools_or_no_action",
            "connected_tools": _get_connected_tools(org_id),
        }

    try:
        from execution.dispatcher import execute_plan as dispatch_plan
        from execution.mcp_client import mcp_enabled

        if not mcp_enabled():
            return {"executed": False, "reason": "mcp_disabled"}

        result = dispatch_plan(plan, "general", org_id=org_id)
        summary = result.get("summary", {})

        # Verify each executed action
        verifications = []
        for action_result in (result.get("actions") or []):
            if action_result.get("status") == "done":
                try:
                    from execution.verification import verify_action
                    ev = verify_action(
                        tool_slug=action_result.get("tool", ""),
                        capability=agent_type.replace("_agent", ""),
                        expected_outcome=action_result.get("description", ""),
                        actual_result=str(action_result.get("result", "") or "")[:1000],
                        trace_id=f"os_{agent_type}_{_now().strftime('%Y%m%d%H%M%S')}",
                        org_id=org_id,
                    )
                    verifications.append({
                        "tool": action_result.get("tool", ""),
                        "outcome": ev.outcome.value if hasattr(ev.outcome, "value") else str(ev.outcome),
                        "confidence": ev.confidence,
                    })
                except Exception as e:
                    log.warning(f"Verification failed for {agent_type}: {e}")

        return {
            "executed": True,
            "done": summary.get("done", 0),
            "failed": summary.get("failed", 0),
            "elapsed_s": summary.get("elapsed_s", 0),
            "verifications": verifications,
        }
    except Exception as e:
        log.error(f"Agent execution failed for {agent_type}: {e}")
        # Audit: failed execution
        try:
            from audit import record_agent_execution
            record_agent_execution(org_id, agent_type, "unknown", str(e)[:150], False)
        except Exception:
            pass
        return {"executed": False, "reason": str(e)[:200]}


# ======================================================================
# Autonomous Business Process Templates
# ======================================================================

# Scheduled autonomous business process templates
BUSINESS_PROCESSES = {
    "morning_brief": {
        "label": "Morning Brief",
        "schedule": "daily_8am",
        "description": "Scan metrics, check pipeline, surface what needs attention today",
        "agent_chain": ["system_agent", "sales_agent", "customer_agent", "growth_agent"],
    },
    "midday_followup": {
        "label": "Midday Follow-up",
        "schedule": "daily_2pm",
        "description": "Follow up on deals stuck >3 days, flag overdue tasks, check customer health",
        "agent_chain": ["sales_agent", "ops_agent", "customer_agent"],
    },
    "evening_wrap": {
        "label": "Evening Wrap",
        "schedule": "daily_7pm",
        "description": "Daily summary: what moved, what's blocked, what needs founder attention",
        "agent_chain": ["ops_agent", "finance_agent", "system_agent"],
    },
    "weekly_strategy": {
        "label": "Weekly Strategy Review",
        "schedule": "weekly_monday",
        "description": "Run full system scan, review OKR progress, generate strategic recommendations",
        "agent_chain": ["strategy_agent", "finance_agent", "product_agent", "system_agent"],
    },
    "weekly_people": {
        "label": "Weekly People Review",
        "schedule": "weekly_friday",
        "description": "Review hiring pipeline, team morale, retention risks",
        "agent_chain": ["hr_agent", "ops_agent"],
    },
    "pipeline_health": {
        "label": "Pipeline Health Check",
        "schedule": "every_4h",
        "description": "Check sales pipeline, flag stuck deals, monitor churn risk",
        "agent_chain": ["sales_agent", "customer_agent", "growth_agent", "marketing_agent"],
    },
    "tech_health": {
        "label": "Tech Health Scan",
        "schedule": "every_6h",
        "description": "Monitor system health, deployment status, incident patterns",
        "agent_chain": ["tech_agent", "system_agent"],
    },
}


def run_business_process(org_id: str, process_id: str) -> dict:
    """Execute a named business process: run agent chain → execute decisions → verify."""
    process = BUSINESS_PROCESSES.get(process_id)
    if not process:
        return {"error": f"Unknown process: {process_id}"}

    run_id = f"osrun_{uuid.uuid4().hex[:12]}"
    start = _now()
    results = {}

    for agent_type in process["agent_chain"]:
        try:
            from agents import run_agent
            decision = run_agent(org_id, agent_type)
        except Exception as e:
            log.warning(f"Agent {agent_type} failed in process {process_id}: {e}")
            results[agent_type] = {"error": str(e)[:100]}
            continue

        if not isinstance(decision, dict) or decision.get("action") == "NOTHING":
            results[agent_type] = {"action": "NOTHING", "executed": False}
            continue

        exec_result = execute_agent_decision(org_id, agent_type, decision)
        results[agent_type] = {
            "decision": decision.get("action"),
            "summary": decision.get("summary", "")[:150],
            "needs_founder": decision.get("needs_founder", False),
            "execution": exec_result,
        }

    elapsed = round((_now() - start).total_seconds(), 1)

    # Persist the run
    run_doc = {
        "id": run_id,
        "org_id": org_id,
        "process_id": process_id,
        "label": process["label"],
        "status": "completed",
        "results": results,
        "agent_count": len(process["agent_chain"]),
        "executed_count": sum(1 for r in results.values() if r.get("execution", {}).get("executed")),
        "elapsed_s": elapsed,
        "created_at": _now().isoformat(),
    }
    if OS_RUNS_COL is not None:
        OS_RUNS_COL.insert_one(run_doc)

    log.info(f"BusinessOS: {process_id} complete — {run_doc['executed_count']}/{run_doc['agent_count']} agents executed in {elapsed}s")

    # Audit trail
    try:
        from audit import record as audit_record
        audit_record(org_id, "business_process_run",
                     f"{process['label']}: {run_doc['executed_count']}/{run_doc['agent_count']} agents executed",
                     details={"process_id": process_id, "elapsed_s": elapsed})
    except Exception:
        pass

    return run_doc


def run_all_processes(org_id: str, process_ids: list[str] = None) -> dict:
    """Run all (or specified) business processes for an org."""
    ids = process_ids or list(BUSINESS_PROCESSES.keys())
    results = {}
    for pid in ids:
        try:
            results[pid] = run_business_process(org_id, pid)
        except Exception as e:
            log.error(f"Process {pid} failed for org {org_id}: {e}")
            results[pid] = {"error": str(e)[:200]}
    return {
        "org_id": org_id,
        "processes_run": len(results),
        "results": results,
    }


# ======================================================================
# Autonomous Business Cycle — the cron entry point
# ======================================================================

def business_cycle(org_id: str) -> dict:
    """The full autonomous business cycle. Called by cron.
    1. Run system scan to detect at-risk functions
    2. Run relevant agents for those functions
    3. Execute agent decisions through connected tools
    4. Verify outcomes
    5. Generate tasks for unresolved issues
    6. Publish dashboard
    """
    start = _now()
    cycle_id = f"cycle_{uuid.uuid4().hex[:12]}"

    # 1. System scan
    scan_result = {}
    try:
        from business_system import init_system_model, persist_system_model, run_signal_scan
        org = orgs_col.find_one({"id": org_id})
        if org and org.get("north_star"):
            model = init_system_model(org)
            persist_system_model(org_id, model)
            scan = run_signal_scan(org_id)
            scan_result = {
                "at_risk_count": scan.get("at_risk_count", 0),
                "healthy_count": scan.get("healthy_count", 0),
            }
            # Generate tasks for at-risk functions
            from execution.bridge import generate_tasks_for_at_risk_functions
            task_ids = generate_tasks_for_at_risk_functions(org_id)
            scan_result["tasks_generated"] = len(task_ids)
    except Exception as e:
        log.warning(f"System scan failed in cycle {cycle_id}: {e}")

    # 2. Run all agents
    agent_results = {}
    try:
        from agents import run_all_agents
        agent_results = run_all_agents(org_id)
    except Exception as e:
        log.warning(f"Agent run failed in cycle {cycle_id}: {e}")

    # 3. Execute agent decisions through tools
    execution_results = {}
    connected = _get_connected_tools(org_id)
    if connected:
        for agent_type, result in (agent_results.get("results", {}) or {}).items():
            if isinstance(result, dict) and result.get("action") not in ("NOTHING", None) and not result.get("needs_founder"):
                try:
                    exec_result = execute_agent_decision(org_id, agent_type, result)
                    execution_results[agent_type] = exec_result
                except Exception as e:
                    execution_results[agent_type] = {"error": str(e)[:100]}

    # 4. Execute approved tasks
    tasks_executed = 0
    try:
        from execution.bridge import execute_approved_tasks
        task_result = execute_approved_tasks(org_id, max_tasks=10)
        tasks_executed = task_result.get("executed", 0)
    except Exception:
        pass

    # 5. OKR refresh
    okr_health = {}
    try:
        from okr_engine import refresh_okr_progress_from_scan
        okr_health = refresh_okr_progress_from_scan(org_id) or {}
    except Exception:
        pass

    elapsed = round((_now() - start).total_seconds(), 1)

    cycle_doc = {
        "id": cycle_id,
        "org_id": org_id,
        "type": "autonomous_cycle",
        "scan": scan_result,
        "agents_run": agent_results.get("agents_run", 0),
        "agents_executed": len(execution_results),
        "tasks_executed": tasks_executed,
        "okr_health": okr_health,
        "connected_tools": len(connected),
        "elapsed_s": elapsed,
        "created_at": _now().isoformat(),
    }
    if OS_RUNS_COL is not None:
        OS_RUNS_COL.insert_one(cycle_doc)

    log.info(f"BusinessOS cycle {cycle_id}: {len(execution_results)} agents executed through {len(connected)} tools, {tasks_executed} tasks, {elapsed}s")

    # Audit trail
    try:
        from audit import record_business_cycle
        record_business_cycle(org_id, cycle_doc["agents_run"], len(execution_results),
                              len(connected), elapsed)
    except Exception:
        pass

    return cycle_doc


def business_cycle_all_orgs() -> dict:
    """Run autonomous business cycle for all orgs with connected tools."""
    results = {}
    try:
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1, "name": 1}):
            try:
                results[org["name"]] = business_cycle(org["id"])
            except Exception as e:
                log.warning(f"Business cycle failed for org {org.get('id')}: {e}")
                results[org.get("name", org.get("id"))] = {"error": str(e)[:200]}
    except Exception as e:
        log.exception(f"business_cycle_all_orgs failed: {e}")
    return {"orgs_processed": len(results), "results": results}


# ======================================================================
# Dashboard — what's running autonomously
# ======================================================================

def os_status(org_id: str) -> dict:
    """Live dashboard: what the Business OS is doing."""
    connected = _get_connected_tools(org_id)

    # Recent runs
    recent_runs = []
    if OS_RUNS_COL is not None:
        recent_runs = list(OS_RUNS_COL.find(
            {"org_id": org_id},
            {"_id": 0, "id": 1, "type": 1, "label": 1, "process_id": 1,
             "agents_run": 1, "agents_executed": 1, "executed_count": 1,
             "connected_tools": 1, "elapsed_s": 1, "created_at": 1},
        ).sort("created_at", -1).limit(10))

    # Agent status
    agent_status = {}
    try:
        from agents import get_agents
        agents = get_agents(org_id)
        for a in agents:
            agent_status[a["type"]] = {
                "role": a.get("role", ""),
                "status": a.get("status", ""),
                "last_run": a.get("last_run"),
                "schedule": a.get("schedule", ""),
                "decisions": a.get("memory", {}).get("decisions_made", 0),
                "actions": a.get("memory", {}).get("actions_taken", 0),
                "alerts": a.get("memory", {}).get("alerts_sent", 0),
            }
    except Exception:
        pass

    # Task summary
    task_counts = {}
    try:
        from execution.tasks import task_summary
        task_counts = task_summary(org_id)
    except Exception:
        pass

    # Learning summary
    learning = {}
    try:
        from execution.verification import learning_summary
        learning = learning_summary(org_id)
    except Exception:
        pass

    return {
        "connected_tools": connected,
        "connected_count": len(connected),
        "processes_available": list(BUSINESS_PROCESSES.keys()),
        "process_count": len(BUSINESS_PROCESSES),
        "recent_runs": recent_runs,
        "agents": agent_status,
        "agent_count": len(agent_status),
        "tasks": task_counts,
        "learning": learning,
    }


def os_decisions(org_id: str, limit: int = 20) -> list:
    """History of all autonomous decisions + their outcomes."""
    if OS_RUNS_COL is None:
        return []
    pipeline = [
        {"$match": {"org_id": org_id}},
        {"$sort": {"created_at": -1}},
        {"$limit": limit},
        {"$project": {"_id": 0, "id": 1, "type": 1, "label": 1, "process_id": 1,
                       "results": 1, "executed_count": 1, "agent_count": 1,
                       "elapsed_s": 1, "created_at": 1}},
    ]
    return list(OS_RUNS_COL.aggregate(pipeline))


# ======================================================================
# Business Outcome Verification — follow-up loop
# ======================================================================

# Founder approval inbox collection
APPROVAL_COL = _db.os_approvals if _db is not None else None

if APPROVAL_COL is not None:
    APPROVAL_COL.create_index("id", unique=True)
    APPROVAL_COL.create_index([("org_id", 1), ("status", 1)])


def verify_business_outcome(execution_id: str, org_id: str, agent_type: str, expected: str, actual: str = None) -> dict:
    """Verify BUSINESS outcome (not just tool status). Runs 24h after execution.
    Uses LLM to assess: did this action actually improve the situation?
    Stores learning regardless of outcome."""
    if not actual:
        # Check 24h later — try to find evidence of outcome
        try:
            from execution.verification import verify_action
            ev = verify_action(
                tool_slug=f"agent_{agent_type}",
                capability="business_outcome",
                expected_outcome=expected,
                actual_result="Outcome pending — no evidence gathered yet",
                trace_id=execution_id,
                org_id=org_id,
                deep_verify=False,
            )
            return {"verified": False, "reason": "too_early", "evidence": ev.model_dump() if hasattr(ev, "model_dump") else {}}
        except Exception:
            return {"verified": False, "reason": "too_early"}

    # Deep verification with LLM
    try:
        from llm_router import verify_call
        prompt = (
            f"BUSINESS ACTION: {expected[:300]}\n"
            f"ACTUAL RESULT: {actual[:1000]}\n\n"
            f"Did this action achieve its business goal? "
            f"Output JSON: {{\"outcome\": \"SUCCESS\"|\"PARTIAL\"|\"FAILURE\", "
            f"\"confidence\": 0.0-1.0, \"insight\": \"one line of what was learned\"}}"
        )
        result = verify_call(
            system="You verify business outcomes. Be honest about success/failure.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
        )
        from llm_client import _extract_json
        verdict = json.loads(_extract_json(result["text"]))

        # Persist learning
        if OS_DECISIONS_COL is not None:
            OS_DECISIONS_COL.update_one(
                {"id": execution_id},
                {"$set": {
                    "outcome_verified": True,
                    "outcome_result": verdict.get("outcome", "UNKNOWN"),
                    "outcome_confidence": verdict.get("confidence", 0.5),
                    "outcome_insight": verdict.get("insight", ""),
                    "verified_at": _now().isoformat(),
                    "verified_by": result.get("model", "unknown"),
                }},
                upsert=True,
            )

        return {"verified": True, **verdict}
    except Exception as e:
        log.warning(f"Outcome verification failed: {e}")
        return {"verified": False, "reason": str(e)[:100]}


# ======================================================================
# Founder Approval Inbox — one-tap actions
# ======================================================================

def request_approval(org_id: str, agent_type: str, role: str, action: dict) -> str:
    """L3-L5 actions that need founder approval. Goes to the approval inbox.
    Founder sees: what the agent wants to do, why, one-tap approve/edit/deny."""
    if APPROVAL_COL is None:
        return ""

    aid = f"approval_{uuid.uuid4().hex[:12]}"
    item = {
        "id": aid,
        "org_id": org_id,
        "from_agent": agent_type,
        "from_role": role,
        "action_type": action.get("action", ""),
        "summary": action.get("summary", "")[:300],
        "recommendation": action.get("recommendation", "")[:300],
        "severity": action.get("severity", "medium"),
        "tool_calls": action.get("_plan", []),
        "estimated_cost_inr": action.get("estimated_cost_inr", 0),
        "status": "pending",
        "founder_action": None,
        "founder_note": "",
        "approved_at": None,
        "executed_at": None,
        "created_at": _now().isoformat(),
    }
    APPROVAL_COL.insert_one(item)
    log.info(f"Approval requested: {aid} from {agent_type} — {action.get('summary', '')[:80]}")
    return aid


def get_pending_approvals(org_id: str) -> list:
    """List pending approval items for the founder. Sorted newest first."""
    if APPROVAL_COL is None:
        return []
    return list(APPROVAL_COL.find(
        {"org_id": org_id, "status": "pending"},
        {"_id": 0},
    ).sort("created_at", -1).limit(50))


def get_approval_summary(org_id: str) -> dict:
    """Quick count for the approval badge."""
    if APPROVAL_COL is None:
        return {"pending": 0, "approved_today": 0}
    return {
        "pending": APPROVAL_COL.count_documents({"org_id": org_id, "status": "pending"}),
        "approved_today": APPROVAL_COL.count_documents({
            "org_id": org_id,
            "status": "approved",
            "approved_at": {"$gte": (_now() - timedelta(days=1)).isoformat()},
        }),
    }


def handle_approval(approval_id: str, action: str, founder_note: str = "") -> dict:
    """Founder approves, edits, or denies an agent's proposed action.
    action: 'approve' | 'deny' | 'edit'
    If approved → auto-execute the action through tools."""
    if APPROVAL_COL is None:
        return {"error": "DB not available"}
    item = APPROVAL_COL.find_one({"id": approval_id})
    if not item:
        return {"error": "Approval not found"}
    if item["status"] != "pending":
        return {"error": f"Already {item['status']}"}

    now = _now().isoformat()
    if action == "deny":
        APPROVAL_COL.update_one({"id": approval_id}, {"$set": {
            "status": "denied", "founder_action": "denied",
            "founder_note": founder_note[:200], "approved_at": now,
        }})
        return {"status": "denied"}

    if action == "approve":
        APPROVAL_COL.update_one({"id": approval_id}, {"$set": {
            "status": "approved", "founder_action": "approved",
            "founder_note": founder_note[:200], "approved_at": now,
        }})
        # Auto-execute the approved action
        org_id = item["org_id"]
        agent_type = item["from_agent"]
        decision = {
            "action": item["action_type"],
            "summary": item["summary"],
            "recommendation": item["recommendation"],
        }
        try:
            exec_result = execute_agent_decision(org_id, agent_type, decision)
            APPROVAL_COL.update_one({"id": approval_id}, {"$set": {
                "executed_at": now,
                "execution_result": exec_result,
            }})
            return {"status": "approved_and_executed", "execution": exec_result}
        except Exception as e:
            return {"status": "approved", "execution_error": str(e)[:200]}

    return {"status": action, "note": "Action recorded"}


# Extend dashboard with approval counts
def os_status_extended(org_id: str) -> dict:
    """Full status with approval inbox."""
    status = os_status(org_id)
    status["approvals"] = get_approval_summary(org_id)
    status["pending_approvals"] = get_pending_approvals(org_id)[:5]
    return status

def ensure_business_os_startup():
    """Idempotent indexes. Called from server startup."""
    if OS_RUNS_COL is not None:
        OS_RUNS_COL.create_index("id", unique=True)
        OS_RUNS_COL.create_index([("org_id", 1), ("created_at", -1)])
    if OS_DECISIONS_COL is not None:
        OS_DECISIONS_COL.create_index("id", unique=True)
        OS_DECISIONS_COL.create_index([("org_id", 1), ("status", 1)])


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    assert len(BUSINESS_PROCESSES) == 7, f"Expected 7 processes, got {len(BUSINESS_PROCESSES)}"
    for pid, proc in BUSINESS_PROCESSES.items():
        assert "agent_chain" in proc, f"{pid} missing agent_chain"
        assert len(proc["agent_chain"]) >= 1, f"{pid} has empty agent_chain"

    plan = _build_execution_plan("sales_agent", {
        "action": "FOLLOW_UP_LEADS",
        "summary": "3 deals stuck >14 days, need follow-up",
        "recommendation": "Send personalized check-in emails to all 3 contacts",
    }, "test_org")
    # Plan may be None if no tools connected — that's valid
    if plan:
        assert len(plan["actions"]) >= 1

    print(f"OK — Business OS: {len(BUSINESS_PROCESSES)} processes, agent execution engine ready")
