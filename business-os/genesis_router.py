"""
Genesis Router — the 15-minute deployment API.

POST /api/genesis/start        → twin + questions
POST /api/genesis/answer       → proposed mission
POST /api/genesis/approve-mission → proposed org
POST /api/genesis/approve-org     → creates company + execs + culture
POST /api/genesis/connect      → tool connection status
POST /api/genesis/launch       → generates tasks → L3 queue
GET  /api/genesis/status       → pipeline progress
"""

import json
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from security import current_user
from db import users_col, orgs_col, members_col, executives_col, genesis_pipelines_col
from genesis import extract_twin, generate_mission, generate_organization, map_capabilities
from execution.tasks import generate_tasks_for_executive, enqueue_task, get_pending_tasks

log = logging.getLogger("genesis.router")
router = APIRouter(prefix="/api/genesis")


# Current UTC timestamp as ISO string
def now_iso():
    return datetime.now(timezone.utc).isoformat()


# ── Pipeline state persists in Mongo — survives restarts, safe for multi-worker ──
def _get_pipe(uid: str) -> Optional[dict]:
    if genesis_pipelines_col is None:
        return None
    return genesis_pipelines_col.find_one({"user_id": uid}, {"_id": 0})


# Upsert pipeline state in Mongo
def _save_pipe(uid: str, pipe: dict) -> None:
    if genesis_pipelines_col is None:
        return
    pipe["user_id"] = uid
    genesis_pipelines_col.update_one({"user_id": uid}, {"$set": pipe}, upsert=True)


# Return the authenticated user
def _require_user(user: dict):
    return user


# ── Models ──
class StartIn(BaseModel):
    vision: str = Field(min_length=10, max_length=5000)

# Payload for challenge-question answers
class AnswerIn(BaseModel):
    answers: dict = Field(default_factory=dict)

# Payload for approved mission fields
class MissionApprovalIn(BaseModel):
    mission: dict
    north_star: str = ""
    target: str = ""
    deadline: str = ""
    priorities: list[str] = Field(default_factory=list)
    decision_rules: str = ""

# Payload for approved org structure
class OrgApprovalIn(BaseModel):
    divisions: list[dict] = Field(default_factory=list)
    culture: list[dict] = Field(default_factory=list)


# ── Pipeline Steps ──

@router.post("/start")
def genesis_start(body: StartIn, user: dict = Depends(current_user)):
    """Step 1 & 2: Extract Digital Twin + generate challenge questions."""
    uid = user["id"]
    twin_data = extract_twin(body.vision)
    pipe = {
        "vision": body.vision,
        "twin": twin_data.get("twin", {}),
        "questions": twin_data.get("questions", []),
        "answers": {},
        "mission": None,
        "org": None,
        "stage": "clarify",
        "started_at": now_iso(),
    }
    _save_pipe(uid, pipe)
    return {
        "twin": pipe["twin"],
        "questions": pipe["questions"],
        "stage": "clarify",
    }


@router.post("/answer")
def genesis_answer(body: AnswerIn, user: dict = Depends(current_user)):
    """Step 3: Process founder's answers + generate mission."""
    uid = user["id"]
    pipe = _get_pipe(uid)
    if not pipe:
        raise HTTPException(404, "No active genesis session. Call /start first.")

    pipe["answers"] = body.answers
    twin = pipe["twin"]
    mission = generate_mission(twin, body.answers)
    pipe["mission"] = mission
    pipe["stage"] = "review_mission"
    _save_pipe(uid, pipe)
    return {
        "mission": mission,
        "stage": "review_mission",
    }


@router.post("/approve-mission")
def genesis_approve_mission(body: MissionApprovalIn, user: dict = Depends(current_user)):
    """Step 4: Founder approves/edits mission, generates organization."""
    uid = user["id"]
    pipe = _get_pipe(uid)
    if not pipe:
        raise HTTPException(404, "No active genesis session.")

    mission = body.dict(exclude_none=True)
    pipe["mission"] = mission
    twin = pipe["twin"]

    org = generate_organization(twin, mission)
    pipe["org"] = org
    pipe["stage"] = "review_org"
    _save_pipe(uid, pipe)
    return {
        "organization": org,
        "capabilities_needed": map_capabilities(twin),
        "stage": "review_org",
    }


@router.post("/approve-org")
def genesis_approve_org(body: OrgApprovalIn, user: dict = Depends(current_user)):
    """Step 5: Founder approves organization. Creates company in DB."""
    uid = user["id"]
    pipe = _get_pipe(uid)
    if not pipe:
        raise HTTPException(404, "No active genesis session.")

    mission = pipe.get("mission", {})
    twin = pipe.get("twin", {})

    # 1. Create the organization
    org_name = mission.get("mission", twin.get("industry", "My Company"))[:120]
    org_id = f"org_{uid[:16]}"
    org_doc = {
        "id": org_id, "name": org_name, "owner_user_id": uid,
        "member_count": 1, "created_at": now_iso(),
        "north_star": mission.get("north_star", ""),
        "target": mission.get("target", ""),
        "deadline": mission.get("deadline", ""),
        "priorities": mission.get("priorities", []),
        "decision_rules": mission.get("decision_rules", ""),
        "strategy_version": 1,
        "organization": {"divisions": body.divisions},
    }

    existing = orgs_col.find_one({"owner_user_id": uid})
    if existing:
        org_id = existing["id"]
        orgs_col.update_one({"id": org_id}, {"$set": org_doc})
    else:
        orgs_col.insert_one(org_doc)
        members_col.insert_one({
            "id": f"mem_{uid[:12]}", "org_id": org_id, "user_id": uid,
            "role": "owner", "status": "active", "joined_at": now_iso(),
        })

    # 2. Create executives
    created_execs = []
    for div in body.divisions:
        for ex in div.get("executives", []):
            ex_id = f"exec_{uid[:8]}_{len(created_execs)}"
            dna = {
                "id": ex_id, "org_id": org_id,
                "role": ex.get("role", "Executive"),
                "department_id": ex.get("department_function", "general"),
                "division_id": div.get("name", ""),
                "mission": ex.get("mission", ""),
                "authority": {
                    "decision_rights": ex.get("decision_rights", []),
                    "spending_limit_inr": ex.get("spending_limit_inr", 50000),
                    "escalation_threshold": "department_impact",
                    "can_hire_specialists": False, "can_create_projects": True,
                    "can_communicate_externally": False,
                },
                "kpis": [{"name": k.get("name", ""), "target": k.get("target", ""),
                          "weight": k.get("weight", 5), "current": None, "trend": "stable"}
                         for k in ex.get("kpis", [])[:3]],
                "knowledge_domains": ex.get("knowledge_domains", []),
                "budget": {"allocated_inr": 0, "spent_inr": 0, "remaining_inr": 0},
                "authority_level": "L3",
                "risk_appetite": "medium", "decision_style": "deliberative",
                "experience": {"projects_led": 0, "projects_completed": 0, "decisions_made": 0,
                               "decisions_with_positive_outcome": 0, "outcome_success_rate": 0.0, "total_impact_inr": 0},
                "performance_history": [], "relationships": [],
                "current_state": {"active_projects": [], "pending_decisions": [], "open_escalations": [], "workload_pct": 0.0},
                "lifecycle": {
                    "status": "probation", "created_at": now_iso(),
                    "probation_ends_at": None, "promoted_at": None, "promoted_from_role": None,
                    "under_review_since": None, "improvement_plan": None,
                    "archived_at": None, "archive_reason": None, "restorable": True,
                    "predecessor_id": None, "successor_id": None,
                },
                "communication_rules": {"response_time_sla_hours": 24, "escalation_path": [], "cc_rules": []},
            }
            dna.pop("_id", None)
            executives_col.insert_one(dna)
            created_execs.append({"id": ex_id, "role": dna["role"], "department": dna["department_id"]})

    # 3. Store culture on org
    if body.culture:
        principles = []
        for i, p in enumerate(body.culture):
            principles.append({
                "id": f"principle_{i+1}",
                "statement": p.get("statement", "")[:300],
                "heuristic": p.get("heuristic", "")[:300],
                "anti_pattern": p.get("anti_pattern", "")[:300],
                "weight": p.get("weight", 5),
            })
        orgs_col.update_one({"id": org_id}, {"$set": {"culture": {
            "principles": principles,
            "generated_at": now_iso(),
            "updated_at": now_iso(),
            "violation_threshold": 3,
        }}})

    pipe["org_id"] = org_id
    pipe["executives"] = created_execs
    pipe["stage"] = "connect_tools"
    _save_pipe(uid, pipe)

    return {
        "org_id": org_id,
        "org_name": org_name,
        "executives_created": len(created_execs),
        "executives": created_execs,
        "capabilities_needed": map_capabilities(twin),
        "stage": "connect_tools",
    }


@router.get("/connect")
def genesis_connect(user: dict = Depends(current_user)):
    """Step 6: REAL tool connection status from the execution runtime — never mocked.
    Honest by design: a toolkit is 'connected' only if the MCP runtime reports it linked."""
    uid = user["id"]
    pipe = _get_pipe(uid) or {}

    needed = map_capabilities(pipe.get("twin", {})) or []
    needed_toolkits = {tk.lower() for c in needed if isinstance(c, dict)
                       for tk in (c.get("toolkits") or [])}

    connections = []
    try:
        from execution.mcp_client import mcp_enabled, linked_toolkits
        linked = {tk["toolkit"].lower(): tk for tk in (linked_toolkits() if mcp_enabled() else [])}
    except Exception as e:
        log.warning(f"Toolkit status lookup failed: {e}")
        linked = {}

    for tk in sorted(needed_toolkits | set(linked.keys())):
        connections.append({
            "toolkit": tk,
            "status": "connected" if tk in linked else "not_connected",
            "needed": tk in needed_toolkits,
        })
    if not connections:
        connections.append({"toolkit": "none", "status": "not_connected",
                            "note": "No execution tools connected yet — tasks will go to the manual queue"})

    return {"connections": connections, "stage": pipe.get("stage", "connect_tools")}


@router.post("/launch")
def genesis_launch(user: dict = Depends(current_user)):
    """Step 7: Generate first-week tasks for all executives. All L3 — awaiting approval."""
    uid = user["id"]
    pipe = _get_pipe(uid)
    if not pipe:
        raise HTTPException(404, "No active genesis session.")

    mission = pipe.get("mission", {})
    execs = pipe.get("executives", [])
    org_id = pipe.get("org_id", "")
    org_doc = orgs_col.find_one({"id": org_id}, {"_id": 0, "name": 1}) or {}
    org_name = org_doc.get("name") or "Your company"

    all_tasks = []
    for ex in execs:
        # Get full executive doc for accurate data
        ex_doc = executives_col.find_one({"id": ex["id"]}) or ex
        tasks = generate_tasks_for_executive(ex_doc, mission)
        for t in tasks:
            tid = enqueue_task(ex["id"], t, org_id=org_id)
            all_tasks.append({"task_id": tid, "executive": ex["role"], "description": t["description"]})

    pipe["tasks_generated"] = len(all_tasks)
    pipe["stage"] = "launched"
    _save_pipe(uid, pipe)

    return {
        "tasks_generated": len(all_tasks),
        "tasks": all_tasks,
        "pending_approvals": len(get_pending_tasks(org_id=org_id)),
        "org_id": org_id,
        "message": f"{org_name} is live. {len(all_tasks)} tasks awaiting your approval. Your executives are ready.",
        "stage": "launched",
    }


@router.get("/status")
def genesis_status(user: dict = Depends(current_user)):
    """Current pipeline progress."""
    uid = user["id"]
    pipe = _get_pipe(uid) or {}
    return {
        "stage": pipe.get("stage", "not_started"),
        "started_at": pipe.get("started_at"),
        "twin_extracted": bool(pipe.get("twin")),
        "mission_generated": bool(pipe.get("mission")),
        "org_generated": bool(pipe.get("org")),
        "executives_created": len(pipe.get("executives", [])),
        "tasks_generated": pipe.get("tasks_generated", 0),
    }
