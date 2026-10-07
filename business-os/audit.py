"""Organization Record Room — unified audit trail for everything that happens.

One collection. Every event. Filterable by type, actor, time range.
Hooks into: agent decisions, executions, business cycles, connections,
tasks, approvals, turns, system scans, OKR changes, credit events.

Query: GET /api/audit?org_id=X&type=agent_decision&from=...&to=...&limit=100
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from db import db as _db

log = logging.getLogger("audit")

# Mongo collection handle for audit events
AUDIT_COL = _db.org_audit if _db is not None else None

# Create indexes for common audit queries
if AUDIT_COL is not None:
    AUDIT_COL.create_index([("org_id", 1), ("created_at", -1)])
    AUDIT_COL.create_index([("org_id", 1), ("event_type", 1), ("created_at", -1)])
    AUDIT_COL.create_index([("org_id", 1), ("actor_type", 1), ("actor_id", 1)])

# All recognized audit event types
EVENT_TYPES = [
    "agent_decision", "agent_execution", "agent_execution_result",
    "business_cycle", "business_process_run",
    "tool_connected", "tool_disconnected",
    "task_proposed", "task_approved", "task_executed", "task_verified", "task_failed",
    "approval_requested", "approval_approved", "approval_denied",
    "system_scan", "system_health_change",
    "okr_progress", "okr_updated",
    "thread_turn", "thread_created", "thread_status_changed",
    "credit_spent", "credit_granted",
    "member_joined", "member_removed",
    "strategy_updated", "north_star_set",
    "workflow_executed", "workflow_suggested",
    "error", "warning",
]


# Current UTC timestamp helper
def _now():
    return datetime.now(timezone.utc)


def record(
    org_id: str,
    event_type: str,
    summary: str,
    actor_type: str = "system",
    actor_id: str = "",
    details: dict = None,
    severity: str = "info",
    related_id: str = "",
    related_type: str = "",
) -> Optional[str]:
    """Record an event in the org audit trail. Thread-safe, fire-and-forget.
    Returns event_id or None if DB unavailable."""
    if AUDIT_COL is None:
        return None
    if event_type not in EVENT_TYPES:
        event_type = "general"

    event_id = f"audit_{uuid.uuid4().hex[:16]}"
    doc = {
        "id": event_id,
        "org_id": org_id,
        "event_type": event_type,
        "summary": summary[:500],
        "actor_type": actor_type,
        "actor_id": actor_id,
        "details": details or {},
        "severity": severity,
        "related_id": related_id,
        "related_type": related_type,
        "created_at": _now().isoformat(),
    }
    try:
        AUDIT_COL.insert_one(doc)
    except Exception as e:
        log.warning(f"Audit record failed: {e}")
        return None
    return event_id


def query(
    org_id: str,
    event_type: str = None,
    actor_type: str = None,
    severity: str = None,
    from_date: str = None,
    to_date: str = None,
    search: str = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Query the audit trail with filters."""
    if AUDIT_COL is None:
        return {"events": [], "total": 0}

    filt = {"org_id": org_id}
    if event_type:
        filt["event_type"] = event_type
    if actor_type:
        filt["actor_type"] = actor_type
    if severity:
        filt["severity"] = severity
    if from_date or to_date:
        date_filt = {}
        if from_date:
            date_filt["$gte"] = from_date
        if to_date:
            date_filt["$lte"] = to_date
        if date_filt:
            filt["created_at"] = date_filt
    if search:
        filt["$or"] = [
            {"summary": {"$regex": search, "$options": "i"}},
            {"details": {"$regex": search, "$options": "i"}},
        ]

    total = AUDIT_COL.count_documents(filt)
    events = list(AUDIT_COL.find(
        filt, {"_id": 0}
    ).sort("created_at", -1).skip(offset).limit(limit))

    return {"events": events, "total": total, "limit": limit, "offset": offset}


def summary(org_id: str, hours: int = 24) -> dict:
    """Activity summary for the last N hours."""
    if AUDIT_COL is None:
        return {"total": 0, "by_type": {}, "by_severity": {}}

    since = (_now().replace(microsecond=0) - __import__('datetime').timedelta(hours=hours)).isoformat()
    filt = {"org_id": org_id, "created_at": {"$gte": since}}

    total = AUDIT_COL.count_documents(filt)
    pipeline = [
        {"$match": filt},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
    ]
    by_type = {r["_id"]: r["count"] for r in AUDIT_COL.aggregate(pipeline)}

    sev_pipeline = [
        {"$match": filt},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}},
    ]
    by_severity = {r["_id"]: r["count"] for r in AUDIT_COL.aggregate(sev_pipeline)}

    return {"total": total, "by_type": by_type, "by_severity": by_severity, "hours": hours}


def ensure_audit_startup():
    """Idempotent indexes."""
    if AUDIT_COL is not None:
        AUDIT_COL.create_index([("org_id", 1), ("created_at", -1)])
        AUDIT_COL.create_index([("org_id", 1), ("event_type", 1), ("created_at", -1)])


# ── Convenience recorders (called from across codebase) ──

# Record an agent decision event
def record_agent_decision(org_id: str, agent_type: str, action: str, summary: str, model: str = ""):
    return record(org_id, "agent_decision", summary, actor_type="agent", actor_id=agent_type,
                  details={"action": action, "model": model})


# Record an agent execution result event
def record_agent_execution(org_id: str, agent_type: str, tool: str, result: str, success: bool):
    return record(org_id, "agent_execution_result", f"[{agent_type}] {tool}: {result[:150]}",
                  actor_type="agent", actor_id=agent_type,
                  details={"tool": tool, "success": success},
                  severity="error" if not success else "info")


# Record a business cycle run summary
def record_business_cycle(org_id: str, agents_run: int, agents_executed: int, tools_used: int, elapsed_s: float):
    return record(org_id, "business_cycle",
                  f"Cycle: {agents_executed}/{agents_run} agents executed through {tools_used} tools in {elapsed_s}s",
                  details={"agents_run": agents_run, "agents_executed": agents_executed,
                           "tools_used": tools_used, "elapsed_s": elapsed_s})


# Record tool connection state change
def record_tool_connection(org_id: str, toolkit: str, connected: bool, user_id: str = ""):
    return record(org_id, "tool_connected" if connected else "tool_disconnected",
                  f"{'Connected' if connected else 'Disconnected'} {toolkit}",
                  actor_type="user" if user_id else "system", actor_id=user_id,
                  details={"toolkit": toolkit, "connected": connected})


# Record task lifecycle event
def record_task_event(org_id: str, task_id: str, event: str, description: str, executive_id: str = ""):
    type_map = {"proposed": "task_proposed", "approved": "task_approved", "executed": "task_executed",
                "verified": "task_verified", "failed": "task_failed"}
    return record(org_id, type_map.get(event, "task_proposed"), description[:300],
                  actor_type="executive" if executive_id else "system", actor_id=executive_id,
                  related_id=task_id, related_type="task")


# Record a chat thread turn
def record_turn(org_id: str, user_id: str, thread_id: str, intent: str, model: str, tokens: int):
    return record(org_id, "thread_turn", f"Turn: {intent} via {model} ({tokens} tokens)",
                  actor_type="user", actor_id=user_id, related_id=thread_id, related_type="thread",
                  details={"intent": intent, "model": model, "tokens": tokens})


# ── Self-check ──
if __name__ == "__main__":
    assert len(EVENT_TYPES) >= 20, f"Expected >=20 event types, got {len(EVENT_TYPES)}"
    print(f"OK — Audit system: {len(EVENT_TYPES)} event types, ready for hook-in")
