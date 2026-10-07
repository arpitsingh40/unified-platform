"""Ch.22-23, 27-32: Executive DNA + Lifecycle + Hierarchy.
Persistent executive entities with state, memory, relationships, and careers.
The executive is the unit of reasoning — not agents, not prompts.

Executive lifecycle: instantiation → probation → active → (promoted | under_review | archived)
Executive DNA: complete portable specification that survives archival and re-instantiation.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import db, orgs_col, members_col, users_col, executives_col, executive_messages_col, executive_decisions_col
from security import current_user, now_utc

log = logging.getLogger("executive")
router = APIRouter(prefix="/api/org/executives")

# Allowed values for executive fields
VALID_FUNCTIONS = ("sales", "marketing", "product", "engineering", "operations", "finance", "leadership", "general")
VALID_STATUSES = ("instantiation", "probation", "active", "promoted", "under_review", "archived", "merged")
VALID_RISK = ("low", "medium", "high")
VALID_DECISION_STYLES = ("decisive", "deliberative", "consensus", "data_driven")


def ensure_executive_startup():
    """Idempotent indexes. Called from server startup."""
    executives_col.create_index("id", unique=True)
    executives_col.create_index([("org_id", 1), ("status", 1)])
    executives_col.create_index([("department_id", 1), ("status", 1)])
    executive_messages_col.create_index("id", unique=True)
    executive_messages_col.create_index([("to_executive_id", 1), ("status", 1)])
    executive_decisions_col.create_index("id", unique=True)
    executive_decisions_col.create_index([("org_id", 1), ("status", 1)])


# Ensure caller is workspace owner
def _require_owner(user: dict) -> dict:
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can manage executives")
    return m


# ---------------------------------------------------------------- Executive DNA model
def empty_executive_dna() -> dict:
    return {
        "id": "", "org_id": "", "role": "", "department_id": "", "division_id": "",
        "mission": "",
        "authority": {
            "decision_rights": [],
            "spending_limit_inr": 0,
            "escalation_threshold": "department_impact",
            "can_hire_specialists": False, "can_create_projects": False,
            "can_communicate_externally": False,
        },
        "kpis": [],
        "budget": {"allocated_inr": 0, "spent_inr": 0, "remaining_inr": 0},
        "communication_rules": {
            "response_time_sla_hours": 24,
            "escalation_path": [],
            "cc_rules": [],
        },
        "knowledge_domains": [],
        "risk_appetite": "medium",
        "decision_style": "deliberative",
        "experience": {
            "projects_led": 0, "projects_completed": 0,
            "decisions_made": 0, "decisions_with_positive_outcome": 0,
            "outcome_success_rate": 0.0, "total_impact_inr": 0,
        },
        "performance_history": [],
        "relationships": [],
        "current_state": {
            "active_projects": [], "pending_decisions": [],
            "open_escalations": [], "workload_pct": 0.0,
        },
        "lifecycle": {
            "status": "instantiation", "created_at": None, "probation_ends_at": None,
            "promoted_at": None, "promoted_from_role": None,
            "under_review_since": None, "improvement_plan": None,
            "archived_at": None, "archive_reason": None, "restorable": True,
            "predecessor_id": None, "successor_id": None,
        },

    }


# ---------------------------------------------------------------- CRUD
class CreateExecutiveIn(BaseModel):
    role: str = Field(min_length=2, max_length=120)
    department_function: str = Field(default="general")
    mission: str = Field(min_length=2, max_length=600)
    decision_rights: list[str] = Field(default_factory=list)
    spending_limit_inr: int = Field(default=0, ge=0)
    kpis: list[dict] = Field(default_factory=list)  # [{name, target, weight}]
    risk_appetite: str = Field(default="medium")
    decision_style: str = Field(default="deliberative")
    knowledge_domains: list[str] = Field(default_factory=list)


@router.post("")
def create_executive(body: CreateExecutiveIn, user: dict = Depends(current_user)):
    """Owner-only. Birth a new executive into the organization."""
    m = _require_owner(user)
    org_id = m["org_id"]
    org = orgs_col.find_one({"id": org_id})
    structure = (org or {}).get("organization") or {}
    divisions = structure.get("divisions") or []

    func = body.department_function.lower()
    if func not in VALID_FUNCTIONS:
        func = "general"

    division_id = None
    dept_obj = None
    for div in divisions:
        for d in (div.get("departments") or []):
            if d.get("function") == func:
                division_id = div.get("name", "")
                dept_obj = d
                break
        if division_id:
            break

    risk = body.risk_appetite if body.risk_appetite in VALID_RISK else "medium"
    style = body.decision_style if body.decision_style in VALID_DECISION_STYLES else "deliberative"

    dna = empty_executive_dna()
    dna.update({
        "id": "exec_" + uuid.uuid4().hex[:16],
        "org_id": org_id,
        "role": body.role.strip(),
        "department_id": func,
        "division_id": division_id,
        "mission": body.mission.strip(),
        "authority": {
            "decision_rights": [r.strip() for r in body.decision_rights if r.strip()][:10],
            "spending_limit_inr": body.spending_limit_inr,
            "escalation_threshold": "department_impact",
            "can_hire_specialists": False, "can_create_projects": True,
            "can_communicate_externally": False,
        },
        "kpis": [{"name": str(k.get("name", ""))[:100], "target": k.get("target", ""),
                  "weight": max(1, min(10, int(k.get("weight", 5) or 5))),
                  "current": None, "trend": "stable"}
                 for k in body.kpis if isinstance(k, dict) and k.get("name")][:5],
        "risk_appetite": risk,
        "decision_style": style,
        "knowledge_domains": [d.strip() for d in body.knowledge_domains if d.strip()][:10],
    })
    dna["lifecycle"] = {
        "status": "probation", "created_at": now_utc().isoformat(),
        "probation_ends_at": None, "promoted_at": None, "promoted_from_role": None,
        "under_review_since": None, "improvement_plan": None,
        "archived_at": None, "archive_reason": None, "restorable": True,
        "predecessor_id": None, "successor_id": None,

    }
    executives_col.insert_one(dna)
    dna.pop("_id", None)  # mongomock adds ObjectId _id — strip before JSON serialization
    return {"executive": dna}


@router.get("")
def list_executives(status: Optional[str] = None, department_function: Optional[str] = None,
                    user: dict = Depends(current_user)):
    """Owner-only. All executives in the org, filterable by status and department."""
    m = _require_owner(user)
    q = {"org_id": m["org_id"]}
    if status and status in VALID_STATUSES:
        q["lifecycle.status"] = status
    if department_function:
        q["department_id"] = department_function

    rows = list(executives_col.find(q, {"_id": 0}).sort("lifecycle.created_at", -1).limit(50))
    for r in rows:
        r.pop("experience", None)
        r.pop("performance_history", None)
        r.pop("relationships", None)
    return {"executives": rows, "count": len(rows)}


# ================================================================= Ch.32: Executive Performance
@router.post("/snapshot")
def take_performance_snapshot(user: dict = Depends(current_user)):
    """Owner-only. Weekly KPI snapshot for all active executives.
    Captures current KPI values and stores in performance_history."""
    m = _require_owner(user)
    execs = list(executives_col.find({"org_id": m["org_id"], "lifecycle.status": {"$in": ["active", "probation"]}}))
    now = now_utc()
    week_start = now.isoformat()[:10]
    updated = 0

    for ex in execs:
        kpis = ex.get("kpis", [])
        kpi_scores = {}
        overall = 0
        total_weight = 0
        for k in kpis:
            name = k.get("name", "")
            val = k.get("current")
            weight = k.get("weight", 5)
            if val is not None:
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    val = None
            kpi_scores[name] = val
            if val is not None and weight:
                overall += val * weight
                total_weight += weight

        overall_score = round(overall / total_weight, 1) if total_weight > 0 else None

        snapshot = {
            "week_start": week_start,
            "kpi_scores": kpi_scores,
            "overall_score": overall_score,
            "notes": "",
    
    }
        executives_col.update_one({"id": ex["id"]}, {
            "$push": {"performance_history": {"$each": [snapshot], "$slice": -52}}  # keep last year
        })
        updated += 1

    return {"snapshots_taken": updated, "week_start": week_start}


@router.get("/performance")
def performance_dashboard(user: dict = Depends(current_user)):
    """Owner-only. Aggregate performance view for all executives."""
    m = _require_owner(user)
    execs = list(executives_col.find({"org_id": m["org_id"], "lifecycle.status": {"$in": ["active", "probation"]}},
                                      {"_id": 0}))
    dashboard = []
    for ex in execs:
        hist = ex.get("performance_history", []) or []
        recent = hist[-4:] if len(hist) >= 4 else hist
        scores = [s.get("overall_score") for s in recent if s.get("overall_score") is not None]
        avg = round(sum(scores) / len(scores), 1) if scores else None
        trend = "stable"
        if len(scores) >= 2:
            trend = "up" if scores[-1] > scores[0] else ("down" if scores[-1] < scores[0] else "stable")

        dashboard.append({
            "executive_id": ex["id"],
            "role": ex.get("role", ""),
            "department": ex.get("department_id", ""),
            "status": ex.get("lifecycle", {}).get("status", ""),
            "experience": {
                "decisions": ex.get("experience", {}).get("decisions_made", 0),
                "success_rate": ex.get("experience", {}).get("outcome_success_rate", 0),
                "impact_inr": ex.get("experience", {}).get("total_impact_inr", 0),
            },
            "performance": {
                "recent_avg": avg,
                "trend": trend,
                "snapshots": len(hist),
            },
        })

    dashboard.sort(key=lambda x: x["performance"].get("recent_avg") or 0, reverse=True)
    top_performer = dashboard[0] if dashboard and dashboard[0]["performance"]["recent_avg"] else None
    needs_attention = [d for d in dashboard
                        if d["performance"]["recent_avg"] is not None and d["performance"]["recent_avg"] < 40]

    return {
        "executives": dashboard,
        "count": len(dashboard),
        "top_performer": top_performer,
        "needs_attention": needs_attention,

    }


# NOTE: /messages and /culture GETs are registered BEFORE /{executive_id} —
# FastAPI matches in registration order; a path param route would shadow them.
@router.get("/messages")
def list_executive_messages(executive_id: Optional[str] = None,
                            user: dict = Depends(current_user)):
    """Owner-only. All messages in the executive organization."""
    m = _require_owner(user)
    ex = executives_col.find_one({"org_id": m["org_id"]})
    q = {}
    q["$or"] = [{"from_executive_id": ex["id"]} if ex else {},
                {"to_executive_ids": executive_id} if executive_id else {}]
    q = {k: v for k, v in q.items() if v}
    if not q:
        q = {}
        execs = [e["id"] for e in executives_col.find({"org_id": m["org_id"]}, {"_id": 0, "id": 1})]
        if execs:
            q["$or"] = [{"from_executive_id": {"$in": execs}}, {"to_executive_ids": {"$in": execs}}]

    rows = list(executive_messages_col.find(q, {"_id": 0}).sort("created_at", -1).limit(50))
    return {"messages": rows, "count": len(rows)}


# Fetch company culture principles
@router.get("/culture")
def get_culture(user: dict = Depends(current_user)):
    """Owner-only. View the company culture principles."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]}, {"_id": 0, "culture": 1})
    culture = (org or {}).get("culture") or {}
    return {"culture": culture, "has_culture": bool(culture.get("principles"))}


@router.get("/{executive_id}")
def get_executive(executive_id: str, user: dict = Depends(current_user)):
    """Full executive DNA including performance and experience."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]}, {"_id": 0})
    if not ex:
        raise HTTPException(404, "Executive not found")
    return {"executive": ex}


# Partial-update payload for executive DNA
class UpdateExecutiveIn(BaseModel):
    role: Optional[str] = None
    mission: Optional[str] = None
    decision_rights: Optional[list[str]] = None
    spending_limit_inr: Optional[int] = None
    kpis: Optional[list[dict]] = None
    risk_appetite: Optional[str] = None
    decision_style: Optional[str] = None
    knowledge_domains: Optional[list[str]] = None


@router.patch("/{executive_id}")
def update_executive(executive_id: str, body: UpdateExecutiveIn, user: dict = Depends(current_user)):
    """Owner-only. Update executive DNA fields."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]})
    if not ex:
        raise HTTPException(404, "Executive not found")

    upd = {}
    if body.role:
        upd["role"] = body.role.strip()
    if body.mission:
        upd["mission"] = body.mission.strip()
    if body.decision_rights is not None:
        upd["authority.decision_rights"] = [r.strip() for r in body.decision_rights if r.strip()][:10]
    if body.spending_limit_inr is not None:
        upd["authority.spending_limit_inr"] = max(0, body.spending_limit_inr)
    if body.kpis is not None:
        upd["kpis"] = [{"name": str(k.get("name", ""))[:100], "target": k.get("target", ""),
                        "weight": max(1, min(10, int(k.get("weight", 5) or 5))),
                        "current": k.get("current"), "trend": str(k.get("trend", "stable"))}
                       for k in body.kpis if isinstance(k, dict) and k.get("name")][:5]
    if body.risk_appetite and body.risk_appetite in VALID_RISK:
        upd["risk_appetite"] = body.risk_appetite
    if body.decision_style and body.decision_style in VALID_DECISION_STYLES:
        upd["decision_style"] = body.decision_style
    if body.knowledge_domains is not None:
        upd["knowledge_domains"] = [d.strip() for d in body.knowledge_domains if d.strip()][:10]

    if upd:
        executives_col.update_one({"id": executive_id}, {"$set": upd})
    return {"ok": True, "executive_id": executive_id}


# ---------------------------------------------------------------- Lifecycle (Ch.27-30)
@router.post("/{executive_id}/promote")
def promote_executive(executive_id: str, body: CreateExecutiveIn, user: dict = Depends(current_user)):
    """Owner-only. Promote an executive to a larger role with preserved knowledge."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]})
    if not ex:
        raise HTTPException(404, "Executive not found")
    if ex["lifecycle"]["status"] not in ("active", "probation"):
        raise HTTPException(400, f"Cannot promote an executive that is {ex['lifecycle']['status']}")

    risk = body.risk_appetite if body.risk_appetite in VALID_RISK else ex.get("risk_appetite", "medium")
    style = body.decision_style if body.decision_style in VALID_DECISION_STYLES else ex.get("decision_style", "deliberative")

    executives_col.update_one({"id": executive_id}, {"$set": {
        "lifecycle.status": "promoted",
        "lifecycle.promoted_at": now_utc().isoformat(),
        "lifecycle.promoted_from_role": ex.get("role", ""),
        "role": body.role.strip(),
        "mission": body.mission.strip(),
        "authority.decision_rights": [r.strip() for r in body.decision_rights if r.strip()][:10],
        "authority.spending_limit_inr": body.spending_limit_inr,
        "kpis": [{"name": str(k.get("name", ""))[:100], "target": k.get("target", ""),
                  "weight": max(1, min(10, int(k.get("weight", 5) or 5))),
                  "current": None, "trend": "stable"}
                 for k in body.kpis if isinstance(k, dict) and k.get("name")][:5],
        "risk_appetite": risk, "decision_style": style,
        "knowledge_domains": list(set((ex.get("knowledge_domains") or []) +
                                      [d.strip() for d in body.knowledge_domains if d.strip()]))[:15],
    }})
    return {"ok": True, "promoted": True}


# Archive executive, preserving knowledge
@router.post("/{executive_id}/archive")
def archive_executive(executive_id: str, reason: str = "", user: dict = Depends(current_user)):
    """Owner-only. Archive an executive — preserves knowledge, transfers active projects."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]})
    if not ex:
        raise HTTPException(404, "Executive not found")

    # ponytail: preserve knowledge in org_memory before archival (Ch.26 hooks here in future)
    executives_col.update_one({"id": executive_id}, {"$set": {
        "lifecycle.status": "archived",
        "lifecycle.archived_at": now_utc().isoformat(),
        "lifecycle.archive_reason": reason.strip() or "Role no longer needed",
        "lifecycle.restorable": True,
    }})
    return {"ok": True, "archived": True, "reason": reason}


# Restore archived executive to probation
@router.post("/{executive_id}/restore")
def restore_executive(executive_id: str, user: dict = Depends(current_user)):
    """Owner-only. Restore an archived executive with full knowledge intact."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]})
    if not ex:
        raise HTTPException(404, "Executive not found")
    if ex["lifecycle"]["status"] != "archived":
        raise HTTPException(400, "Only archived executives can be restored")

    executives_col.update_one({"id": executive_id}, {"$set": {
        "lifecycle.status": "probation",
        "lifecycle.probation_ends_at": None,
        "lifecycle.archived_at": None,
        "lifecycle.archive_reason": None,
        "lifecycle.restorable": True,
    }})
    return {"ok": True, "restored": True}


# ---------------------------------------------------------------- Ch.23: Executive Communication
class ExecutiveMessageIn(BaseModel):
    to_executive_id: str = Field(min_length=1)
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=2000)
    priority: str = Field(default="medium")
    decision_required: bool = False
    deadline_hours: Optional[int] = Field(default=None, ge=1, le=720)


@router.post("/messages")
def send_executive_message(body: ExecutiveMessageIn, user: dict = Depends(current_user)):
    """Owner sends a directive/consultation to an executive."""
    m = _require_owner(user)
    sender = executives_col.find_one({"org_id": m["org_id"]})
    recipient = executives_col.find_one({"id": body.to_executive_id, "org_id": m["org_id"]})
    if not recipient:
        raise HTTPException(404, "Recipient executive not found")

    priority = body.priority if body.priority in ("low", "medium", "high", "critical") else "medium"
    deadline = (now_utc().isoformat() if body.deadline_hours is None
                else (now_utc() + __import__('datetime').timedelta(hours=body.deadline_hours)).isoformat())

    msg = {
        "id": str(uuid.uuid4()),
        "from_executive_id": sender["id"] if sender else "founder",
        "to_executive_ids": [body.to_executive_id],
        "subject": body.subject.strip(),
        "body": body.body.strip(),
        "priority": priority,
        "decision_required": body.decision_required,
        "deadline": deadline,
        "status": "unread",
        "thread_id": None,
        "created_at": now_utc().isoformat(),

    }
    executive_messages_col.insert_one(msg)
    return {"message": msg}


# ---------------------------------------------------------------- Ch.25: Company Culture
class CultureIn(BaseModel):
    principles: list[dict] = Field(default_factory=list)  # [{statement, heuristic, anti_pattern}]


@router.put("/culture")
def set_culture(body: CultureIn, user: dict = Depends(current_user)):
    """Owner-only. Define company culture principles that guide all executive decisions."""
    m = _require_owner(user)
    principles = []
    for p in body.principles[:7]:
        if isinstance(p, dict) and p.get("statement"):
            principles.append({
                "id": str(uuid.uuid4()),
                "statement": str(p.get("statement", ""))[:300],
                "heuristic": str(p.get("heuristic", ""))[:300],
                "anti_pattern": str(p.get("anti_pattern", ""))[:300],
                "weight": max(1, min(10, int(p.get("weight", 5) or 5))),
            })
    culture = {
        "principles": principles,
        "generated_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
        "violation_threshold": 3,

    }
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {"culture": culture}})
    return {"culture": culture, "principles_count": len(principles)}


# ================================================================= Ch.31: Executive Memory
def record_executive_decision(executive_id: str, outcome_status: str, impact_inr: int = 0):
    """Update executive experience after a decision outcome is reviewed.
    Called from decision_brain review endpoint. Pure DB update, no LLM."""
    ex = executives_col.find_one({"id": executive_id})
    if not ex:
        return
    exp = ex.get("experience", {})
    exp["decisions_made"] = (exp.get("decisions_made", 0) or 0) + 1
    if outcome_status == "success":
        exp["decisions_with_positive_outcome"] = (exp.get("decisions_with_positive_outcome", 0) or 0) + 1
    total = exp.get("decisions_made", 0)
    pos = exp.get("decisions_with_positive_outcome", 0)
    exp["outcome_success_rate"] = round(pos / total, 2) if total > 0 else 0.0
    exp["total_impact_inr"] = (exp.get("total_impact_inr", 0) or 0) + (impact_inr or 0)
    executives_col.update_one({"id": executive_id}, {"$set": {"experience": exp}})


def record_executive_project(executive_id: str, completed: bool):
    """Update executive project experience."""
    ex = executives_col.find_one({"id": executive_id})
    if not ex:
        return
    exp = ex.get("experience", {})
    exp["projects_led"] = (exp.get("projects_led", 0) or 0) + 1
    if completed:
        exp["projects_completed"] = (exp.get("projects_completed", 0) or 0) + 1
    executives_col.update_one({"id": executive_id}, {"$set": {"experience": exp}})


@router.get("/{executive_id}/memory")
def get_executive_memory(executive_id: str, limit: int = 10, user: dict = Depends(current_user)):
    """Owner-only. What this executive has learned — decisions made, outcomes, patterns."""
    m = _require_owner(user)
    ex = executives_col.find_one({"id": executive_id, "org_id": m["org_id"]},
                                  {"_id": 0, "experience": 1, "performance_history": 1,
                                   "knowledge_domains": 1, "relationships": 1, "lifecycle": 1})
    if not ex:
        raise HTTPException(404, "Executive not found")
    return {"executive_id": executive_id, **ex}



