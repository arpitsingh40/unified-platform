"""Execution Dispatcher — plan → atomic actions → MCP gateway execution.
Accepts execution plans from SALAAR/engine, queues actions respecting
dependencies, executes via self-hosted MCP gateway, handles retries, reports progress.
"""
import time
import logging
from datetime import datetime, timezone

from .mcp_client import call_tool, mcp_enabled, tools_for_department

log = logging.getLogger("execution.dispatcher")

# Retry budget for failed tool calls
MAX_RETRIES = int(__import__('os').environ.get("MCP_MAX_RETRIES", "3"))
RETRY_DELAY_BASE = 2  # seconds, exponential backoff


# Action lifecycle status constants
class ActionStatus:
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


# ISO timestamp helper
def now_iso():
    return datetime.now(timezone.utc).isoformat()


# Governance gate helper — lazy import so dispatcher never hard-depends on governance
def _governed(org_id) -> dict:
    try:
        from governance import execution_gate
        return execution_gate(org_id, 0)
    except Exception:
        return {"allowed": True, "reason": "ok", "kill_switch": False,
                "dry_run": False, "spend_this_week": 0.0, "cap": 0}


# Execute plan actions respecting dependencies and retries
def execute_plan(plan: dict, department_function: str = "general",
                 on_progress=None, org_id: str = None) -> dict:
    """Execute a complete plan: N actions, respecting dependencies.
    Returns {actions: [{status, result, error, elapsed_ms}], summary: {total, done, failed}}.

    Plan shape: {"goal": "...", "actions": [{tool, args, depends_on, description}]}
    """
    if not mcp_enabled():
        return {"error": "MCP disabled — set service tokens (e.g. GMAIL_ACCESS_TOKEN) in .env", "actions": []}

    actions = plan.get("actions", [])
    if not actions:
        return {"actions": [], "summary": {"total": 0, "done": 0, "failed": 0}}

    # Governance gate: kill switch / weekly cap — block the whole plan before anything runs
    gate = _governed(org_id)
    if not gate["allowed"]:
        skipped = [{"tool": a.get("tool", ""), "description": a.get("description", ""),
                    "status": ActionStatus.SKIPPED, "error": gate["reason"]} for a in actions]
        return {"error": gate["reason"], "actions": skipped,
                "summary": {"total": len(actions), "done": 0, "failed": 0,
                            "skipped": len(actions), "blocked_by": "governance",
                            "kill_switch": gate["kill_switch"]},
                "dry_run": gate["dry_run"]}

    # Dry-run mode: record planned steps, never call any tool
    dry_run = gate["dry_run"]

    # Wire 4: budget enforcement before execution
    if org_id:
        try:
            from execution.bridge import enforce_budget, record_spend
            estimated_cost = sum(int(a.get("estimated_cost_inr", 0) or 0) for a in actions)
            if estimated_cost > 0 and not enforce_budget(org_id, estimated_cost):
                return {"error": "BUDGET_EXCEEDED", "actions": [],
                        "summary": {"total": len(actions), "done": 0, "failed": 0,
                                    "skipped": len(actions), "budget_blocked": True}}
        except Exception:
            pass  # budget check is advisory when bridge is unavailable

    available_tools = {t["name"] for t in tools_for_department(department_function)}
    results = [None] * len(actions)
    statuses = [ActionStatus.PENDING] * len(actions)
    retry_counts = [0] * len(actions)

    def dependencies_met(i):
        for dep_idx in actions[i].get("depends_on", []):
            if isinstance(dep_idx, int) and 0 <= dep_idx < len(results):
                if statuses[dep_idx] != ActionStatus.DONE:
                    return False
        return True

    def tool_available(tool_name):
        # ponytail: allow any tool from a connected toolkit (prefix match is enough)
        # The CLI accepts tools even if they're not in `tools list` output
        if not available_tools:
            return True
        if tool_name in available_tools:
            return True
        # Also check by toolkit prefix — CLI may have tools not in list output
        from .mcp_client import linked_toolkits
        connected_prefixes = [tk["toolkit"].lower() for tk in linked_toolkits()]
        return any(tool_name.lower().startswith(p) for p in connected_prefixes)

    t0 = time.time()
    completed = 0
    max_iterations = len(actions) * 3  # safety valve

    for _ in range(max_iterations):
        if completed >= len(actions):
            break

        progressed = False
        for i in range(len(actions)):
            if statuses[i] != ActionStatus.PENDING:
                continue
            if not dependencies_met(i):
                continue

            action = actions[i]
            tool_name = action.get("tool", "")
            args = action.get("args", {})

            if not tool_available(tool_name):
                statuses[i] = ActionStatus.SKIPPED
                results[i] = {"error": f"Tool '{tool_name}' not authorized for {department_function}"}
                completed += 1
                progressed = True
                continue

            # Dry-run: record the planned step without invoking the tool
            if dry_run:
                statuses[i] = ActionStatus.SKIPPED
                results[i] = {"tool": tool_name, "description": action.get("description", ""),
                              "status": ActionStatus.SKIPPED, "dry_run": True,
                              "planned_args": args,
                              "result": f"[DRY RUN] would call {tool_name}"}
                completed += 1
                progressed = True
                continue

            # Re-check the kill switch per action — it can flip mid-plan
            if _governed(org_id)["kill_switch"]:
                statuses[i] = ActionStatus.FAILED
                results[i] = {"tool": tool_name, "description": action.get("description", ""),
                              "status": ActionStatus.FAILED,
                              "error": "Kill switch activated mid-execution — action aborted"}
                completed += 1
                progressed = True
                continue

            statuses[i] = ActionStatus.RUNNING
            if on_progress:
                on_progress(i, len(actions), action.get("description", tool_name))

            result = call_tool(tool_name, args)
            # Special: SMARTDECIGEN_BUILD routes to capability platform
            if tool_name == "SMARTDECIGEN_BUILD" and "error" in result:
                try:
                    from capabilities import execute_capability
                    build_result = execute_capability(
                        args.get("description", ""),
                        deploy_target=args.get("deploy_target", "github"),
                    )
                    if build_result.get("url") or build_result.get("status") == "complete":
                        result = {"result": f"Built: {build_result.get('label', 'artifact')}",
                                  "successful": True, "execution_time_ms": 0}
                except Exception:
                    pass
            if "error" in result and retry_counts[i] < MAX_RETRIES:
                retry_counts[i] += 1
                delay = RETRY_DELAY_BASE ** retry_counts[i]
                log.warning(f"Action {i} '{tool_name}' failed (attempt {retry_counts[i]}), retrying in {delay}s")
                time.sleep(delay)
                statuses[i] = ActionStatus.PENDING  # reset to retry
                continue

            statuses[i] = ActionStatus.DONE if "error" not in result else ActionStatus.FAILED
            results[i] = {
                "tool": tool_name,
                "description": action.get("description", ""),
                "status": statuses[i],
                "result": result.get("result", "") if "result" in result else None,
                "error": result.get("error") if "error" in result else None,
                "elapsed_ms": result.get("execution_time_ms", 0),
                "retries": retry_counts[i],
                "executed_at": now_iso(),
            }
            completed += 1
            progressed = True

        if not progressed:
            break  # deadlock — remaining actions have unmet dependencies

    # Mark any stragglers
    for i in range(len(actions)):
        if statuses[i] == ActionStatus.PENDING:
            statuses[i] = ActionStatus.FAILED
            results[i] = {"error": "Dependency never resolved or deadlock", "status": "failed"}

    elapsed = round(time.time() - t0, 2)
    summary = {
        "total": len(actions),
        "done": sum(1 for s in statuses if s == ActionStatus.DONE),
        "failed": sum(1 for s in statuses if s == ActionStatus.FAILED),
        "skipped": sum(1 for s in statuses if s == ActionStatus.SKIPPED),
        "elapsed_s": elapsed,
    }
    if dry_run:
        summary["dry_run"] = True

    log.info(f"Plan executed: {summary['done']}/{summary['total']} done ({summary['failed']} failed) in {elapsed}s")
    return {"actions": results, "summary": summary, "plan_goal": plan.get("goal", "")}


# Pre-flight validation of execution plan
def validate_plan(plan: dict) -> list:
    """Pre-flight validation. Returns list of issues (empty = valid)."""
    issues = []
    actions = plan.get("actions", [])
    if not actions:
        issues.append("Plan has no actions")
    for i, action in enumerate(actions):
        if not action.get("tool"):
            issues.append(f"Action {i}: missing 'tool' field")
        if not isinstance(action.get("args"), dict):
            issues.append(f"Action {i}: 'args' must be a dict")
        deps = action.get("depends_on", [])
        if not isinstance(deps, list):
            issues.append(f"Action {i}: 'depends_on' must be a list")
        for d in deps:
            if not isinstance(d, int) or d >= len(actions) or d < 0:
                issues.append(f"Action {i}: invalid dependency index {d}")
    return issues
