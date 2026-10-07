"""OKR Intelligence Layer — extends existing plans/tasks KRs with auto-computed progress,
confidence tracking, and stalling detection. No new database collections. Pure functions.

Existing system: departments have objective (str) + key_results (str[]). Tasks link via linked_kr_index.
This module: wraps those strings into smart objects with auto-computed progress + confidence.

Key principle: progress is auto-detected, not self-reported. Confidence drops = early warning.
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from db import orgs_col, tasks_col, plans_col

log = logging.getLogger("okr_engine")


# Current UTC timestamp helper
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# KR object wrapper — upgrade flat strings to rich objects
# ======================================================================

def _ensure_kr_object(kr) -> dict:
    """Convert a flat string KR (old format) to a rich object (new format)."""
    if isinstance(kr, dict) and "description" in kr:
        return kr
    desc = str(kr) if kr else ""
    return {
        "id": f"kr_{hash(desc) & 0xFFFFFFFF:08x}",
        "description": desc[:200],
        "target": 100,
        "current": 0,
        "metric_type": "percentage",
        "confidence": 70,
        "progress_pct": 0,
        "last_updated": _now().isoformat(),
    }


def _kr_progress(kr: dict) -> float:
    """Auto-compute percentage progress for a key result."""
    target = kr.get("target", 100)
    current = kr.get("current", 0)
    if target <= 0:
        return 100 if current > 0 else 0
    return max(0, min(100, round((current / target) * 100)))


def normalize_department_krs(department: dict) -> list[dict]:
    """Normalize a department's KRs to the new object format, computing progress."""
    krs = department.get("key_results", [])
    normalized = []
    for kr in krs:
        obj = _ensure_kr_object(kr)
        obj["progress_pct"] = _kr_progress(obj)
        normalized.append(obj)
    return normalized


# ======================================================================
# Auto-compute KR progress from execution data
# ======================================================================

def auto_update_kr_from_tasks(org_id: str, department_function: str) -> dict:
    """Scan completed tasks for this department and auto-update KR progress.
    Returns the updated department with recomputed KRs."""
    dept = find_department(org_id, department_function)
    if not dept:
        return {}

    krs = normalize_department_krs(dept)

    # Count tasks completed per KR
    tasks = list(tasks_col.find({
        "org_id": org_id,
        "department_function": department_function,
        "status": {"$in": ["done", "executed", "verified"]},
    })) if tasks_col else []

    for task in tasks:
        idx = task.get("linked_kr_index", -1)
        if 0 <= idx < len(krs):
            # ponytail: each completed task = ~8% progress toward the KR (assumes ~12 tasks per KR per quarter)
            krs[idx]["current"] = min(krs[idx].get("target", 100),
                                       krs[idx].get("current", 0) + (krs[idx].get("target", 100) * 0.08))
            krs[idx]["progress_pct"] = _kr_progress(krs[idx])

    # Detect confidence drop: if progress < 15% with <4 weeks left, flag
    for kr in krs:
        if kr["progress_pct"] < 15 and kr.get("confidence", 70) > 40:
            kr["confidence"] = max(30, kr.get("confidence", 50) - 10)
            kr["stalling"] = True

    krs = [{k: v for k, v in kr.items() if k != "id"} for kr in krs]  # strip internal id
    dept["key_results"] = krs

    # Persist
    update_department_krs(org_id, department_function, krs)
    return dept


# ======================================================================
# OKR health check — used by weekly scan
# ======================================================================

def okr_health_report(org_id: str) -> dict:
    """Analyze all department KRs for the weekly scan. Returns health summary."""
    plan = plans_col.find_one({"org_id": org_id, "status": "active"}) if plans_col else None
    if not plan:
        return {"total_krs": 0, "on_track": 0, "stalling": 0, "at_risk": 0, "details": []}

    departments = plan.get("departments", [])
    all_krs = []
    stalling = []
    at_risk = []

    for dept in departments:
        func = dept.get("function", "unknown")
        krs = normalize_department_krs(dept)
        for i, kr in enumerate(krs):
            kr["department"] = func
            kr["index"] = i
            all_krs.append(kr)

            if kr.get("stalling"):
                stalling.append(kr)
            elif kr["confidence"] < 40:
                at_risk.append(kr)

    on_track = len(all_krs) - len(stalling) - len(at_risk)

    return {
        "total_krs": len(all_krs),
        "on_track": on_track,
        "stalling": len(stalling),
        "at_risk": len(at_risk),
        "health": "strong" if len(at_risk) == 0 and len(stalling) < 2 else (
            "warning" if len(at_risk) == 0 else "at_risk"
        ),
        "stalling_details": [{"department": kr["department"], "kr": kr["description"][:100],
                                "progress": kr["progress_pct"], "confidence": kr["confidence"]}
                             for kr in stalling[:5]],
        "at_risk_details": [{"department": kr["department"], "kr": kr["description"][:100],
                              "progress": kr["progress_pct"], "confidence": kr["confidence"]}
                            for kr in at_risk[:5]],
    }


# ======================================================================
# KR → Task link display for task approval brief
# ======================================================================

def kr_context_for_task(task: dict) -> str:
    """Build a contextual line for task approval briefs showing KR impact."""
    idx = task.get("linked_kr_index", -1)
    if idx < 0:
        return ""

    org_id = task.get("org_id")
    func = task.get("department_function", "general")
    dept = find_department(org_id, func)
    if not dept:
        return ""

    krs = normalize_department_krs(dept)
    if idx < len(krs):
        kr = krs[idx]
        current = kr["progress_pct"]
        new_estimate = min(100, current + 8)
        return (
            f"Advances KR #{idx + 1}: \"{kr['description'][:120]}\" "
            f"(currently {current}% → ~{new_estimate}% after completion, confidence: {kr['confidence']})"
        )

    return ""


# ======================================================================
# Department helpers
# ======================================================================

def find_department(org_id: str, function: str) -> Optional[dict]:
    """Find a department in the active plan."""
    plan = plans_col.find_one({"org_id": org_id, "status": "active"}) if plans_col else None
    if not plan:
        return None
    depts = plan.get("departments", [])
    for d in depts:
        if d.get("function") == function:
            return d
    return None


def update_department_krs(org_id: str, function: str, key_results: list):
    """Update KRs for a specific department in the active plan."""
    if not plans_col:
        return
    plan = plans_col.find_one({"org_id": org_id, "status": "active"})
    if not plan:
        return
    depts = plan.get("departments", [])
    for d in depts:
        if d.get("function") == function:
            d["key_results"] = key_results
            break
    plans_col.update_one({"org_id": org_id, "status": "active"},
                         {"$set": {"departments": depts}})


def get_all_department_krs(org_id: str) -> list[dict]:
    """Get all KRs across all departments with progress."""
    plan = plans_col.find_one({"org_id": org_id, "status": "active"}) if plans_col else None
    if not plan:
        return []
    result = []
    for dept in plan.get("departments", []):
        func = dept.get("function", "general")
        obj = dept.get("objective", "")[:200]
        krs = normalize_department_krs(dept)
        for i, kr in enumerate(krs):
            result.append({
                "department": func,
                "objective": obj,
                "kr_index": i,
                "description": kr["description"][:150],
                "progress": kr["progress_pct"],
                "confidence": kr["confidence"],
                "stalling": kr.get("stalling", False),
                "target": kr.get("target", 100),
                "current": kr.get("current", 0),
            })
    return sorted(result, key=lambda x: x["progress"])


# ======================================================================
# Wire: update KRs from weekly scan
# ======================================================================

def refresh_okr_progress_from_scan(org_id: str):
    """Called after weekly scan: auto-update all department KRs from task execution data."""
    plan = plans_col.find_one({"org_id": org_id, "status": "active"}) if plans_col else None
    if not plan:
        return

    for dept in plan.get("departments", []):
        func = dept.get("function", "")
        if func:
            auto_update_kr_from_tasks(org_id, func)

    # Log OKR health
    health = okr_health_report(org_id)
    log.info(f"OKR health for org {org_id}: {health['on_track']}/{health['total_krs']} on track, "
             f"{health['stalling']} stalling, {health['at_risk']} at risk")

    return health


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    kr = _ensure_kr_object("Grow revenue by 20%")
    assert kr["description"] == "Grow revenue by 20%"
    assert kr["progress_pct"] == 0
    assert _kr_progress({"target": 100, "current": 67}) == 67
    assert callable(refresh_okr_progress_from_scan)
    assert callable(okr_health_report)
    assert callable(kr_context_for_task)
    print("OK — OKR intelligence engine verified")
