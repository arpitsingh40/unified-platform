"""Phase 1 — Organizations (company workspaces).

A founder creates ONE organization, then invites team members via a join link.
The org is the container that will later hold (Phase 2) the hidden strategy / North Star
and (Phase 3) the shared, founder-trained knowledge base. This module only builds the
container + membership + invites. No LLM, no credits.

Roles:
  owner  -> the company founder (distinct from platform `is_admin` / Founder OS)
  member -> a team member who joined via an invite link

Data model (all UUID ids, never Mongo ObjectId):
  organizations : {id, name, owner_user_id, member_count, created_at, + Phase-2 strategy fields}
  org_members   : {id, org_id, user_id, role, status(active|removed), joined_at}
  org_invites   : {id, org_id, code, email, role, created_by, status(pending|accepted|revoked),
                   created_at, accepted_by, accepted_at}
"""
import os
import json
import uuid
import secrets
import logging
from datetime import timedelta, datetime, timezone

from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr

from db import orgs_col, members_col, invites_col, users_col, decisions_col, plans_col, tasks_col, threads_col, org_memory_col, resource_requests_col, projects_col, automation_templates_col
from security import current_user, now_utc
from engine import client, _extract_json, PRIMARY_MODEL

log = logging.getLogger("org")

router = APIRouter(prefix="/api/org", tags=["organizations"])

# Base URL used to build join links
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "").rstrip("/")


# ----------------------------------------------------------------- startup
def ensure_org_startup():
    """Idempotent indexes for the org layer. Called from server startup."""
    orgs_col.create_index("id", unique=True)
    orgs_col.create_index("owner_user_id")
    members_col.create_index("id", unique=True)
    members_col.create_index([("org_id", 1), ("user_id", 1)], unique=True)
    members_col.create_index([("user_id", 1), ("status", 1)])
    invites_col.create_index("id", unique=True)
    invites_col.create_index("code", unique=True)
    invites_col.create_index([("org_id", 1), ("status", 1)])
    plans_col.create_index("id", unique=True)
    plans_col.create_index([("org_id", 1), ("status", 1)])
    tasks_col.create_index("id", unique=True)
    tasks_col.create_index([("org_id", 1), ("week_start", 1)])
    tasks_col.create_index([("org_id", 1), ("assigned_to", 1), ("status", 1)])


# ----------------------------------------------------------------- models
class CreateOrgIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)


# Payload for creating an invite
class InviteIn(BaseModel):
    email: Optional[EmailStr] = None
    role: str = "member"


# Payload for accepting an invite code
class JoinIn(BaseModel):
    code: str = Field(min_length=4, max_length=80)


class StrategyIn(BaseModel):
    """Founder-only hidden steering. NEVER exposed to members."""
    north_star: str = Field(default="", max_length=2000)
    target: str = Field(default="", max_length=300)
    deadline: str = Field(default="", max_length=120)
    priorities: list[str] = Field(default_factory=list)
    decision_rules: str = Field(default="", max_length=4000)
    # Layer 3: transparent pacing inputs (founder-entered, used only for arithmetic projection).
    current_arr: Optional[float] = Field(default=None, ge=0)
    target_arr: Optional[float] = Field(default=None, ge=0)


class ProgressIn(BaseModel):
    """Founder-only quick update of where the company is now (drives the Goal -> Progress tracker).
    Does NOT change the strategy or bump strategy_version - it only logs forward motion."""
    current_arr: float = Field(ge=0)


# ----------------------------------------------------------------- helpers
# Find the caller's active membership row
def _active_membership(user: dict) -> Optional[dict]:
    return members_col.find_one({"user_id": user["id"], "status": "active"})


# Ensure caller is workspace owner
def _require_owner(user: dict) -> dict:
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can do this")
    return m


def _org_view(org: dict, role: str) -> dict:
    """Member-safe org view. NEVER leaks the hidden strategy (Phase 2)."""
    return {
        "id": org["id"],
        "name": org["name"],
        "role": role,
        "member_count": int(org.get("member_count", 1)),
        "created_at": org.get("created_at"),
        "is_owner": role == "owner",
        # founder-only flag the UI uses to reveal the (Phase-2) strategy console
        "strategy_set": bool(org.get("north_star")),
    }


# Build the shareable join link
def _join_url(code: str) -> str:
    base = FRONTEND_BASE_URL or ""
    return f"{base}/join/{code}"


# Sanitized invite payload for clients
def _invite_view(inv: dict) -> dict:
    return {
        "id": inv["id"],
        "code": inv["code"],
        "email": inv.get("email") or "",
        "role": inv.get("role", "member"),
        "status": inv.get("status", "pending"),
        "created_at": inv.get("created_at"),
        "accepted_at": inv.get("accepted_at"),
        "join_url": _join_url(inv["code"]),
    }


# ----------------------------------------------------------------- endpoints
@router.post("")
def create_org(body: CreateOrgIn, user: dict = Depends(current_user)):
    """Create a company workspace. Caller becomes the owner (founder)."""
    if _active_membership(user):
        raise HTTPException(409, "You are already part of an organization")
    org = {
        "id": str(uuid.uuid4()),
        "name": body.name.strip(),
        "owner_user_id": user["id"],
        "member_count": 1,
        "created_at": now_utc(),
        # ---- Phase-2 hidden strategy (founder-only, never sent to members) ----
        "north_star": "", "target": "", "deadline": "",
        "priorities": [], "decision_rules": "", "strategy_updated_at": None,
        # ---- Layer 0/5: strategy versioning + pacing inputs ----
        "strategy_version": 0, "current_arr": None, "target_arr": None,
    }
    orgs_col.insert_one(org)
    members_col.insert_one({
        "id": str(uuid.uuid4()), "org_id": org["id"], "user_id": user["id"],
        "role": "owner", "status": "active", "joined_at": now_utc(),
    })
    users_col.update_one({"id": user["id"]}, {"$set": {"org_id": org["id"], "org_role": "owner"}})
    return _org_view(org, "owner")


@router.get("")
def my_org(user: dict = Depends(current_user)):
    """The caller's current workspace + their role. 404 if they have none."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(404, "You are not part of any organization yet")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return _org_view(org, m["role"])


@router.get("/members")
def list_members(user: dict = Depends(current_user)):
    """Owner-only roster of the workspace."""
    m = _require_owner(user)
    rows = list(members_col.find({"org_id": m["org_id"], "status": "active"}).sort("joined_at", 1))
    out = []
    for r in rows:
        u = users_col.find_one({"id": r["user_id"]}, {"_id": 0, "name": 1, "email": 1, "last_login_at": 1})
        out.append({
            "user_id": r["user_id"],
            "name": (u or {}).get("name", ""),
            "email": (u or {}).get("email", ""),
            "role": r["role"],
            "joined_at": r.get("joined_at"),
            "last_login_at": (u or {}).get("last_login_at"),
        })
    return {"members": out, "count": len(out)}


@router.delete("/members/{member_user_id}")
def remove_member(member_user_id: str, user: dict = Depends(current_user)):
    """Owner removes a member. Cannot remove the owner or themselves."""
    m = _require_owner(user)
    if member_user_id == user["id"]:
        raise HTTPException(400, "The owner cannot remove themselves")
    target = members_col.find_one({"org_id": m["org_id"], "user_id": member_user_id, "status": "active"})
    if not target:
        raise HTTPException(404, "Member not found")
    if target["role"] == "owner":
        raise HTTPException(400, "Cannot remove the owner")
    members_col.update_one({"id": target["id"]}, {"$set": {"status": "removed", "removed_at": now_utc()}})
    users_col.update_one({"id": member_user_id}, {"$set": {"org_id": None, "org_role": None}})
    orgs_col.update_one({"id": m["org_id"]}, {"$inc": {"member_count": -1}})
    return {"removed": True, "user_id": member_user_id}


@router.post("/invites")
def create_invite(body: InviteIn, user: dict = Depends(current_user)):
    """Owner creates a shareable join link (optionally tied to an email)."""
    m = _require_owner(user)
    code = secrets.token_urlsafe(9)
    inv = {
        "id": str(uuid.uuid4()),
        "org_id": m["org_id"],
        "code": code,
        "email": (str(body.email).lower() if body.email else ""),
        "role": "member",
        "created_by": user["id"],
        "status": "pending",
        "created_at": now_utc(),
        "accepted_by": None, "accepted_at": None,
    }
    invites_col.insert_one(inv)
    return _invite_view(inv)


@router.get("/invites")
def list_invites(user: dict = Depends(current_user)):
    """Owner sees all invites for the workspace."""
    m = _require_owner(user)
    rows = list(invites_col.find({"org_id": m["org_id"]}).sort("created_at", -1))
    return {"invites": [_invite_view(r) for r in rows]}


@router.post("/invites/{code}/revoke")
def revoke_invite(code: str, user: dict = Depends(current_user)):
    """Owner revokes a pending invite link."""
    m = _require_owner(user)
    inv = invites_col.find_one({"code": code, "org_id": m["org_id"]})
    if not inv:
        raise HTTPException(404, "Invite not found")
    if inv["status"] != "pending":
        raise HTTPException(409, f"Invite is already {inv['status']}")
    invites_col.update_one({"id": inv["id"]}, {"$set": {"status": "revoked"}})
    return {"revoked": True, "code": code}


@router.get("/invites/{code}")
def lookup_invite(code: str):
    """PUBLIC (no auth): the join landing page shows the org name before sign-in."""
    inv = invites_col.find_one({"code": code})
    if not inv or inv.get("status") != "pending":
        return {"valid": False}
    org = orgs_col.find_one({"id": inv["org_id"]}, {"_id": 0, "name": 1})
    return {
        "valid": True,
        "org_name": (org or {}).get("name", "this workspace"),
        "role": inv.get("role", "member"),
        "email": inv.get("email") or "",
    }


@router.post("/join")
def join_org(body: JoinIn, user: dict = Depends(current_user)):
    """Authenticated user accepts an invite and joins the workspace as a member."""
    if _active_membership(user):
        raise HTTPException(409, "You are already part of an organization")
    inv = invites_col.find_one({"code": body.code})
    if not inv:
        raise HTTPException(404, "Invite link is invalid")
    if inv["status"] != "pending":
        raise HTTPException(410, f"This invite link is {inv['status']}")
    org = orgs_col.find_one({"id": inv["org_id"]})
    if not org:
        raise HTTPException(404, "Organization no longer exists")
    members_col.insert_one({
        "id": str(uuid.uuid4()), "org_id": org["id"], "user_id": user["id"],
        "role": "member", "status": "active", "joined_at": now_utc(),
    })
    users_col.update_one({"id": user["id"]}, {"$set": {"org_id": org["id"], "org_role": "member"}})
    orgs_col.update_one({"id": org["id"]}, {"$inc": {"member_count": 1}})
    invites_col.update_one({"id": inv["id"]}, {"$set": {
        "status": "accepted", "accepted_by": user["id"], "accepted_at": now_utc(),
    }})
    return _org_view(org, "member")


# ----------------------------------------------------------------- hidden strategy (the moat)
def _strategy_view(org: dict) -> dict:
    return {
        "north_star": org.get("north_star", "") or "",
        "target": org.get("target", "") or "",
        "deadline": org.get("deadline", "") or "",
        "priorities": list(org.get("priorities", []) or []),
        "decision_rules": org.get("decision_rules", "") or "",
        "strategy_updated_at": org.get("strategy_updated_at"),
        "strategy_set": bool(org.get("north_star")),
        "strategy_version": org.get("strategy_version", 0),
        "current_arr": org.get("current_arr"),
        "target_arr": org.get("target_arr"),
    }


@router.get("/strategy")
def get_strategy(user: dict = Depends(current_user)):
    """Owner-only. The confidential North Star + priorities + rules. NEVER returned to members."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return _strategy_view(org)


@router.put("/strategy")
def set_strategy(body: StrategyIn, user: dict = Depends(current_user)):
    """Owner-only. Saves the hidden steering that silently guides every member's decisions.
    Layer 5: a meaningful change to the strategy bumps strategy_version, so every decision is
    stamped with the strategy that was active when it was made (before/after comparisons)."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    priorities = [p.strip() for p in body.priorities if isinstance(p, str) and p.strip()][:8]
    # bump the version only when the steering content actually changed (not on a no-op save)
    prev = (org.get("north_star", ""), org.get("target", ""), org.get("deadline", ""),
            tuple(org.get("priorities", []) or []), org.get("decision_rules", ""))
    nxt = (body.north_star.strip(), body.target.strip(), body.deadline.strip(),
           tuple(priorities), body.decision_rules.strip())
    cur_ver = int(org.get("strategy_version", 0) or 0)
    new_ver = cur_ver + 1 if (nxt != prev or cur_ver == 0) else cur_ver
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {
        "north_star": body.north_star.strip(),
        "target": body.target.strip(),
        "deadline": body.deadline.strip(),
        "priorities": priorities,
        "decision_rules": body.decision_rules.strip(),
        "current_arr": body.current_arr,
        "target_arr": body.target_arr,
        "strategy_version": new_ver,
        "strategy_updated_at": now_utc(),
    }})
    # Wire: auto-initialize system model when strategy is first set or updated
    try:
        from business_system import init_system_model, persist_system_model
        fresh_org = orgs_col.find_one({"id": m["org_id"]})
        if fresh_org:
            model = init_system_model(fresh_org)
            persist_system_model(m["org_id"], model)
    except Exception as e:
        log.warning(f"system model init failed on strategy save: {e}")
    org = orgs_col.find_one({"id": m["org_id"]})
    if body.current_arr is not None:
        _append_arr_snapshot(m["org_id"], body.current_arr)
    return _strategy_view(org)


# ----------------------------------------------------------------- goal -> progress tracker (founder-only)
PROGRESS_HISTORY_CAP = 36


def _append_arr_snapshot(org_id: str, arr) -> None:
    """Log a point on the founder's progress curve (idempotent against an identical last value)."""
    try:
        arr = float(arr)
    except (TypeError, ValueError):
        return
    org = orgs_col.find_one({"id": org_id}, {"_id": 0, "arr_history": 1})
    hist = list((org or {}).get("arr_history", []) or [])
    if hist and isinstance(hist[-1], dict) and hist[-1].get("arr") == arr:
        return  # no movement, don't clutter the curve
    hist.append({"arr": arr, "at": now_utc().isoformat()})
    orgs_col.update_one({"id": org_id}, {"$set": {"arr_history": hist[-PROGRESS_HISTORY_CAP:]}})


# Label progress percentage in words
def _progress_status(pct):
    if pct is None:
        return "Not started yet"
    if pct >= 100:
        return "Goal reached"
    if pct >= 90:
        return "Almost there"
    if pct >= 60:
        return "Closing in"
    if pct >= 25:
        return "Building momentum"
    if pct > 0:
        return "Just getting started"
    return "Not started yet"


def _goal_progress(org: Optional[dict]) -> Optional[dict]:
    """Transparent arithmetic Goal -> Progress view. Founder-only. Not an AI forecast.
    Returns None when there is no numeric target to measure against."""
    if not org:
        return None
    ca, ta = org.get("current_arr"), org.get("target_arr")
    if not ta or ta <= 0:
        return None
    ca = ca or 0
    progress_pct = round(100 * ca / ta)
    gap_pct = round(100 * (ta - ca) / ca) if ca and ca > 0 else None
    raw_hist = list(org.get("arr_history", []) or [])
    history = [{"arr": h.get("arr"), "at": h.get("at")} for h in raw_hist if isinstance(h, dict)]
    return {
        "north_star": (org.get("north_star") or "").strip(),
        "target": (org.get("target") or "").strip(),
        "deadline": (org.get("deadline") or "").strip(),
        "current_arr": ca,
        "target_arr": ta,
        "remaining": max(0, ta - ca),
        "progress_pct": progress_pct,
        "gap_pct": gap_pct,
        "status": _progress_status(progress_pct),
        "history": history[-12:],
        "note": "Arithmetic only (current ÷ target). Not a forecast.",
    }


@router.get("/progress")
def get_progress(user: dict = Depends(current_user)):
    """Owner-only. The Goal -> Progress snapshot for the founder dashboard."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return {"goal_progress": _goal_progress(org)}


@router.post("/progress")
def set_progress(body: ProgressIn, user: dict = Depends(current_user)):
    """Owner-only. Quick 'where are we now' update. Logs a point on the progress curve and
    recomputes the gap. Does NOT touch the strategy or strategy_version."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {"current_arr": body.current_arr,
                                                       "progress_updated_at": now_utc()}})
    _append_arr_snapshot(m["org_id"], body.current_arr)
    org = orgs_col.find_one({"id": m["org_id"]})
    return {"goal_progress": _goal_progress(org)}


# ----------------------------------------------------------------- founder cockpit (private clarity)
# Collect alignment scores from rows
def _scores_of(rows):
    out = []
    for r in rows:
        a = r.get("strategic_alignment")
        if isinstance(a, dict) and isinstance(a.get("score"), int):
            out.append(a["score"])
    return out


def _effectiveness_by_function(org_id):
    """Layer 3: per-function decision count, avg alignment, and correlational effectiveness %."""
    rows = list(decisions_col.find({"org_id": org_id},
                                   {"_id": 0, "function": 1, "strategic_alignment": 1, "outcome": 1}))
    teams = {}
    for r in rows:
        f = r.get("function") or "general"
        t = teams.setdefault(f, {"function": f, "decisions": 0, "_sc": [], "_oc": []})
        t["decisions"] += 1
        a = r.get("strategic_alignment")
        if isinstance(a, dict) and isinstance(a.get("score"), int):
            t["_sc"].append(a["score"])
        oc = r.get("outcome")
        if isinstance(oc, dict) and oc.get("status") in ("success", "partial", "failed"):
            t["_oc"].append(oc["status"])
    out = []
    for f, t in teams.items():
        sc, oc = t["_sc"], t["_oc"]
        out.append({
            "function": f, "decisions": t["decisions"],
            "avg_alignment": round(sum(sc) / len(sc)) if sc else None,
            "outcomes_scored": len(oc),
            "effectiveness_pct": round(100 * (oc.count("success") + 0.5 * oc.count("partial")) / len(oc)) if oc else None,
        })
    out.sort(key=lambda x: (x["avg_alignment"] is None, x["avg_alignment"] if x["avg_alignment"] is not None else 0))
    return out


def _pacing(org):
    """Layer 3: transparent arithmetic gap from founder-entered ARR. Not an AI forecast."""
    ca, ta = org.get("current_arr"), org.get("target_arr")
    if not ca or not ta or ca <= 0 or ta <= 0:
        return None
    gap_pct = round(100 * (ta - ca) / ca)
    return {"current_arr": ca, "target_arr": ta, "deadline": org.get("deadline", "") or "",
            "gap_pct": gap_pct,
            "note": f"Arithmetic only: to reach the target, ARR must grow {gap_pct}% from here. Not a forecast."}


@router.get("/cockpit")
def cockpit(user: dict = Depends(current_user)):
    """Owner-only. The private view: alignment, drift, execution, momentum. Members never see this."""
    m = _require_owner(user)
    org_id = m["org_id"]
    org = orgs_col.find_one({"id": org_id})
    base = {"org_id": org_id}
    since7 = now_utc() - timedelta(days=7)

    total = decisions_col.count_documents(base)
    last7 = decisions_col.count_documents({**base, "created_at": {"$gte": since7}})

    scored_rows = list(decisions_col.find(
        {**base, "strategic_alignment.score": {"$ne": None}},
        {"_id": 0, "strategic_alignment": 1},
    ))
    scores = _scores_of(scored_rows)
    avg_align = round(sum(scores) / len(scores)) if scores else None
    high = sum(1 for x in scores if x >= 70)
    medium = sum(1 for x in scores if 40 <= x < 70)
    low = sum(1 for x in scores if x < 40)

    committed = decisions_col.count_documents({**base, "committed_action": {"$ne": None}})
    done = decisions_col.count_documents({**base, "status": "done"})
    dropped = decisions_col.count_documents({**base, "status": "dropped"})
    open_count = decisions_col.count_documents({**base, "status": "open", "committed_action": {"$ne": None}})
    follow_through = round(100 * done / (done + dropped)) if (done + dropped) > 0 else None

    members = list(members_col.find({"org_id": org_id, "status": "active"}).sort("joined_at", 1))
    per_member = []
    for mm in members:
        u = users_col.find_one({"id": mm["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        mrows = list(decisions_col.find({**base, "user_id": mm["user_id"]},
                                        {"_id": 0, "strategic_alignment": 1, "status": 1}))
        msc = _scores_of(mrows)
        per_member.append({
            "user_id": mm["user_id"], "name": (u or {}).get("name", ""), "email": (u or {}).get("email", ""),
            "role": mm["role"], "decisions": len(mrows),
            "avg_alignment": (round(sum(msc) / len(msc)) if msc else None),
            "done": sum(1 for r in mrows if r.get("status") == "done"),
        })

    drift = list(decisions_col.find(
        {**base, "strategic_alignment.score": {"$lt": 40}},
        {"_id": 0, "id": 1, "user_name": 1, "question": 1, "strategic_alignment": 1, "created_at": 1},
    ).sort("created_at", -1).limit(10))

    needs_attention = []
    if org:
        na_rows = list(decisions_col.find(
            {"$or": [
                {**base, "strategic_alignment.score": {"$lt": 40}},
                {**base, "strategic_alignment.confidence": "low", "strategic_alignment.score": {"$lt": 70}},
            ]},
            {"_id": 0, "id": 1, "user_name": 1, "question": 1, "strategic_alignment": 1, "committed_action": 1, "created_at": 1},
        ).sort("created_at", -1).limit(10))
        for na in na_rows:
            al = na.get("strategic_alignment") or {}
            needs_attention.append({
                "id": na["id"], "user_name": na.get("user_name", ""),
                "question": (na.get("question") or "")[:200],
                "score": al.get("score"), "reason": al.get("reason", ""),
                "confidence": al.get("confidence"), "basis": al.get("basis", ""),
                "action": na.get("committed_action", "") or "",
            })
    low_conf_count = sum(1 for r in scored_rows
                         if (r.get("strategic_alignment") or {}).get("confidence") in ("low", None))

    # in-flight committed actions across the team (drives the founder's live timers)
    now = now_utc()

    def _iso(dt):
        return dt.isoformat() if hasattr(dt, "isoformat") else dt

    active_rows = list(decisions_col.find(
        {**base, "status": "open", "committed_action": {"$ne": None}, "due_at": {"$ne": None}},
        {"_id": 0, "id": 1, "user_name": 1, "committed_action": 1, "due_at": 1},
    ).sort("due_at", 1).limit(25))
    
    def _is_overdue(due_at):
        """Check if due_at is overdue, handling both offset-aware and offset-naive datetimes"""
        if not due_at:
            return False
        if isinstance(due_at, datetime):
            if due_at.tzinfo is None:
                due_at = due_at.replace(tzinfo=timezone.utc)
            return due_at < now
        return False
    
    active_actions = [{
        "id": r["id"], "user_name": r.get("user_name") or "Member",
        "action": r.get("committed_action"), "due_at": _iso(r.get("due_at")),
        "overdue": _is_overdue(r.get("due_at")),
    } for r in active_rows]
    overdue = sum(1 for a in active_actions if a["overdue"])

    # results the team has actually achieved (founder + member both see the outcome)
    result_rows = list(decisions_col.find(
        {**base, "status": "done", "result": {"$ne": None}},
        {"_id": 0, "id": 1, "user_name": 1, "committed_action": 1, "next_action": 1,
         "result": 1, "result_at": 1},
    ).sort("result_at", -1).limit(12))
    results_feed = [{
        "id": r["id"], "user_name": r.get("user_name") or "Member",
        "action": r.get("committed_action") or r.get("next_action") or "",
        "result": r.get("result"), "result_at": _iso(r.get("result_at")),
    } for r in result_rows]

    # ---- Layer 1: outcome effectiveness (correlational) ----
    oc_rows = list(decisions_col.find(
        {**base, "outcome.status": {"$in": ["success", "partial", "failed"]}},
        {"_id": 0, "outcome": 1, "alignment_band": 1}))
    n_oc = len(oc_rows)
    n_succ = sum(1 for r in oc_rows if r["outcome"]["status"] == "success")
    n_part = sum(1 for r in oc_rows if r["outcome"]["status"] == "partial")
    n_fail = sum(1 for r in oc_rows if r["outcome"]["status"] == "failed")
    eff_pct = round(100 * (n_succ + 0.5 * n_part) / n_oc) if n_oc else None
    effectiveness = {"scored": n_oc, "success": n_succ, "partial": n_part, "failed": n_fail,
                     "effectiveness_pct": eff_pct}

    # ---- Layer 2: alignment calibration (does a high alignment score actually predict success?) ----
    def _succ_rate(band):
        b = [r for r in oc_rows if r.get("alignment_band") == band]
        if not b:
            return None, 0
        return round(100 * sum(1 for r in b if r["outcome"]["status"] == "success") / len(b)), len(b)
    hi_rate, _hi_n = _succ_rate("high")
    lo_rate, _lo_n = _succ_rate("low")
    lift = (hi_rate - lo_rate) if (hi_rate is not None and lo_rate is not None) else None
    predictive = bool(n_oc >= 12 and lift is not None and lift > 0)
    calibration = {"high_success_rate": hi_rate, "low_success_rate": lo_rate, "lift": lift,
                   "samples": n_oc, "predictive": predictive,
                   "note": "Alignment is a DIAGNOSTIC until proven predictive (positive lift with enough samples)."}

    # ---- Layer 3: per-team rollup, alignment trend, transparent pacing ----
    team_alignment = _effectiveness_by_function(org_id)
    recent_scored = _scores_of(list(decisions_col.find(
        {**base, "strategic_alignment.score": {"$ne": None}, "created_at": {"$gte": since7}},
        {"_id": 0, "strategic_alignment": 1})))
    prior_scored = _scores_of(list(decisions_col.find(
        {**base, "strategic_alignment.score": {"$ne": None}, "created_at": {"$lt": since7}},
        {"_id": 0, "strategic_alignment": 1})))
    recent_avg = round(sum(recent_scored) / len(recent_scored)) if recent_scored else None
    prior_avg = round(sum(prior_scored) / len(prior_scored)) if prior_scored else None
    align_trend = (recent_avg - prior_avg) if (recent_avg is not None and prior_avg is not None) else None
    pacing = _pacing(org)

    # ---- Layer 5: Rs impact from reviewed decisions ----
    imp_pipe = list(decisions_col.aggregate([
        {"$match": {**base, "impact_inr": {"$ne": None}}},
        {"$group": {"_id": None, "total": {"$sum": "$impact_inr"}, "n": {"$sum": 1}, "positive": {"$sum": {"$cond": [{"$gte": ["$impact_inr", 0]}, 1, 0]}}}}]))
    impact = {"total_inr": int(imp_pipe[0]["total"]) if imp_pipe else 0,
              "reviewed": int(imp_pipe[0]["n"]) if imp_pipe else 0,
              "positive": int(imp_pipe[0]["positive"]) if imp_pipe else 0}

    # ---- Layer 4: deterministic contradiction detection (declared vs observed) ----
    prox_rows = list(decisions_col.find({**base, "revenue_proximity": {"$ne": None}}, {"_id": 0, "revenue_proximity": 1}))
    internal_share = round(100 * sum(1 for r in prox_rows if r["revenue_proximity"] == "internal") / len(prox_rows)) if prox_rows else None
    contradictions = []
    if overdue >= 2:
        contradictions.append({"title": "Committed but not done",
                               "evidence": f"{overdue} committed actions are overdue.", "severity": "high"})
    if follow_through is not None and follow_through < 60 and (done + dropped) >= 5:
        contradictions.append({"title": "Low follow-through",
                               "evidence": f"Only {follow_through}% of acted decisions were completed.", "severity": "high"})
    prio_text = (" ".join(org.get("priorities", []) or []) + " " + (org.get("north_star", "") or "")).lower()
    growth_focus = any(w in prio_text for w in ("revenue", "growth", "arr", "sales", "customer", "enterprise", "acqui"))
    if growth_focus and internal_share is not None and internal_share >= 60:
        contradictions.append({"title": "Declared growth, internal effort",
                               "evidence": f"{internal_share}% of decisions are internal-facing despite a growth-focused strategy.",
                               "severity": "medium"})
    if align_trend is not None and align_trend <= -8:
        contradictions.append({"title": "Alignment slipping",
                               "evidence": f"Average alignment fell {abs(align_trend)} points vs the prior period.",
                               "severity": "medium"})

    return {
        "north_star": _strategy_view(org),
        "totals": {"decisions": total, "last_7d": last7, "members": len(members)},
        "alignment": {"avg": avg_align, "high": high, "medium": medium, "low": low, "scored": len(scores),
                     "low_confidence_count": low_conf_count},
        "needs_attention": needs_attention,
        "execution": {"committed": committed, "open": open_count, "done": done,
                      "dropped": dropped, "overdue": overdue, "follow_through_pct": follow_through},
        "effectiveness": effectiveness,
        "calibration": calibration,
        "team_alignment": team_alignment,
        "alignment_trend": align_trend,
        "pacing": pacing,
        "goal_progress": _goal_progress(org),
        "contradictions": contradictions,
        "per_member": per_member,
        "drift": drift,
        "impact": impact,
        "active_actions": active_actions,
        "results": results_feed,
    }


# ----------------------------------------------------------------- momentum trend (Upgrade 1)
@router.get("/cockpit/trend")
def cockpit_trend(weeks: int = 8, user: dict = Depends(current_user)):
    """Owner-only. Weekly momentum: alignment, decisions, follow-through over time."""
    m = _require_owner(user)
    org_id = m["org_id"]
    base = {"org_id": org_id}
    weeks = max(1, min(weeks, 26))
    now = now_utc()
    weeks_out = []
    for i in range(weeks - 1, -1, -1):
        monday = (now - timedelta(days=now.weekday() + 7 * i)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = monday + timedelta(days=7)
        wdec = list(decisions_col.find(
            {**base, "created_at": {"$gte": monday, "$lt": end}},
            {"_id": 0, "strategic_alignment": 1, "status": 1, "committed_action": 1}))
        scores = [r.get("strategic_alignment", {}).get("score") for r in wdec
                  if isinstance(r.get("strategic_alignment"), dict) and r["strategic_alignment"].get("score") is not None]
        done = sum(1 for r in wdec if r.get("status") == "done")
        dropped = sum(1 for r in wdec if r.get("status") == "dropped")
        acted = done + dropped
        weeks_out.append({
            "week_start": monday.isoformat()[:10],
            "decisions": len(wdec),
            "avg_alignment": round(sum(scores) / len(scores)) if scores else None,
            "committed": sum(1 for r in wdec if r.get("committed_action")),
            "done": done,
            "dropped": dropped,
            "follow_through_pct": round(100 * done / acted) if acted else None,
        })
    latest = weeks_out[-1] if weeks_out else None
    prev = weeks_out[-2] if len(weeks_out) > 1 else None
    delta = lambda k: (latest[k] - prev[k]) if (latest and prev and latest.get(k) is not None and prev.get(k) is not None) else None
    return {"weeks": weeks_out,
            "deltas": {"avg_alignment": delta("avg_alignment"),
                       "follow_through_pct": delta("follow_through_pct"),
                       "decisions": delta("decisions")}}

# ----------------------------------------------------------------- Layer 6: autonomous planning (human-gated)
DEP_FUNCTIONS = ("sales", "marketing", "product", "engineering", "operations", "finance", "leadership", "general")


# Normalize a department function label
def norm_dep_function(f):
    f = (f or "general").strip().lower()
    return f if f in DEP_FUNCTIONS else "general"


# LLM system prompt for objective-cascade drafts
PLAN_SYSTEM = (
    "You are a strategy operator. Given a company's North Star, priorities, and what has historically "
    "worked per function, draft an objective cascade: ONE company objective, then a short objective plus "
    "2-3 measurable key results for each relevant function. Ground proposals in the historical "
    "effectiveness data provided (favour functions and plays that have actually worked). Be concrete and "
    "numeric where possible. This is a DRAFT for a human to ratify, never a final plan. "
    'Return ONLY JSON, no fences: {"company_objective": "...", "departments": [{"function": '
    '"sales|marketing|product|engineering|operations|finance|leadership", "objective": "...", '
    '"key_results": [{"description": "...", "target": 100, "metric_type": "percentage|number|boolean"}]}]}'
)


# Payload to request a plan draft
class PlanDraftIn(BaseModel):
    target: str = Field(min_length=2, max_length=300)


# Compute per-department plan adherence
def _plan_adherence(org_id, plan):
    since = plan.get("activated_at") or plan.get("created_at")
    q = {"org_id": org_id}
    if since:
        q["created_at"] = {"$gte": since}
    rows = list(decisions_col.find(q, {"_id": 0, "function": 1, "strategic_alignment": 1, "outcome": 1}))
    by_fn = {}
    for r in rows:
        f = r.get("function") or "general"
        d = by_fn.setdefault(f, {"_sc": [], "_oc": [], "n": 0})
        d["n"] += 1
        a = r.get("strategic_alignment")
        if isinstance(a, dict) and isinstance(a.get("score"), int):
            d["_sc"].append(a["score"])
        oc = r.get("outcome")
        if isinstance(oc, dict) and oc.get("status") in ("success", "partial", "failed"):
            d["_oc"].append(oc["status"])
    depts = []
    for dep in plan.get("departments", []) or []:
        f = dep.get("function", "general")
        d = by_fn.get(f, {"_sc": [], "_oc": [], "n": 0})
        oc = d["_oc"]
        depts.append({**dep, "decisions": d["n"],
                      "avg_alignment": round(sum(d["_sc"]) / len(d["_sc"])) if d["_sc"] else None,
                      "effectiveness_pct": round(100 * (oc.count("success") + 0.5 * oc.count("partial")) / len(oc)) if oc else None})
    total_dec = sum(x["n"] for x in by_fn.values())
    return depts, total_dec


# Build client-safe plan payload
def _plan_view(plan, org_id):
    out = {k: plan.get(k) for k in ("id", "target", "status", "company_objective", "created_at", "activated_at")}
    if plan.get("status") == "active":
        depts, total_dec = _plan_adherence(org_id, plan)
        out["departments"] = depts
        out["decisions_since_activation"] = total_dec
    else:
        out["departments"] = plan.get("departments", [])
    return out


@router.post("/plan/draft")
def draft_plan(body: PlanDraftIn, user: dict = Depends(current_user)):
    """Owner-only. AI DRAFTS an objective cascade grounded in what has worked; a human must ratify it."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    eff = _effectiveness_by_function(org["id"])
    eff_text = "\n".join(
        f"- {e['function']}: {e['decisions']} decisions, avg alignment {e['avg_alignment']}, "
        f"effectiveness {e['effectiveness_pct']}% (n={e['outcomes_scored']})" for e in eff) or "(no history yet)"
    prio = "; ".join(org.get("priorities", []) or []) or "(none set)"
    prompt = (
        f"NORTH STAR: {org.get('north_star','') or '(not set)'}\n"
        f"TARGET: {org.get('target','')} {org.get('deadline','')}\n"
        f"PRIORITIES: {prio}\n"
        f"DECISION RULES: {org.get('decision_rules','') or '(none)'}\n"
        f"NEW OBJECTIVE THE FOUNDER WANTS: {body.target.strip()}\n\n"
        f"HISTORICAL EFFECTIVENESS BY FUNCTION (ground the plan in this):\n{eff_text}\n"
    )
    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1600,
                                     system=[{"type": "text", "text": PLAN_SYSTEM}],
                                     messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"plan draft failed: {e}")
        raise HTTPException(502, "Could not draft a plan right now. Try again.")
    depts = []
    for d in (data.get("departments") or [])[:8]:
        if not isinstance(d, dict):
            continue
        # Normalize KRs: support both old flat strings and new rich objects
        krs = []
        for k in (d.get("key_results") or [])[:5]:
            if isinstance(k, dict) and k.get("description"):
                krs.append({
                    "description": str(k.get("description", ""))[:200],
                    "target": float(k.get("target", 100)),
                    "current": float(k.get("current", 0)),
                    "metric_type": str(k.get("metric_type", "percentage"))[:20],
                    "confidence": 70,
                    "progress_pct": 0,
                })
            elif str(k).strip():
                krs.append({
                    "description": str(k).strip()[:200],
                    "target": 100, "current": 0,
                    "metric_type": "percentage",
                    "confidence": 70, "progress_pct": 0,
                })
        depts.append({"function": norm_dep_function(d.get("function")),
                      "objective": str(d.get("objective", ""))[:600], "key_results": krs})
    plan = {"id": str(uuid.uuid4()), "org_id": org["id"], "target": body.target.strip(),
            "status": "draft", "created_at": now_utc(), "activated_at": None, "created_by": user["id"],
            "company_objective": str(data.get("company_objective", ""))[:800], "departments": depts}
    plans_col.insert_one(plan)
    return _plan_view(plan, org["id"])


@router.get("/plan")
def get_plan(user: dict = Depends(current_user)):
    """Owner-only. The active ratified plan (with adherence) + the latest draft awaiting ratification."""
    m = _require_owner(user)
    org_id = m["org_id"]
    active = plans_col.find_one({"org_id": org_id, "status": "active"})
    draft = plans_col.find_one({"org_id": org_id, "status": "draft"}, sort=[("created_at", -1)])
    return {"active": _plan_view(active, org_id) if active else None,
            "draft": _plan_view(draft, org_id) if draft else None}


@router.post("/plan/{plan_id}/ratify")
def ratify_plan(plan_id: str, user: dict = Depends(current_user)):
    """Owner-only human ratification gate: a generated plan goes live ONLY when a human approves it."""
    m = _require_owner(user)
    org_id = m["org_id"]
    p = plans_col.find_one({"id": plan_id, "org_id": org_id})
    if not p:
        raise HTTPException(404, "Plan not found")
    plans_col.update_many({"org_id": org_id, "status": "active"}, {"$set": {"status": "archived"}})
    org = orgs_col.find_one({"id": org_id})
    plans_col.update_one({"id": plan_id}, {"$set": {
        "status": "active", "activated_at": now_utc(),
        "mission_version": (org or {}).get("strategy_version", 0),  # Ch.33: traceability
    }})
    p = plans_col.find_one({"id": plan_id})
    return _plan_view(p, org_id)


# ----------------------------------------------------------------- weekly OKR tasks (execution layer)

TASK_GENERATION_SYSTEM = (
    "You are a task operator for a company using OKRs. The hierarchy is:\n"
    "FOUNDER'S VISION (North Star) → Company Quarterly Objective → Department OKRs → Weekly Tasks\n\n"
    "Every task must trace back to the founder's vision. Given the founder's vision, the quarterly "
    "company objective, each department's objectives and key results, and the available team members "
    "with their functions, generate 3-7 specific weekly tasks for the coming week for EACH department.\n\n"
    "Each task must:\n"
    "- Be completable in one week by a single person\n"
    "- Directly contribute to one of the department's key results\n"
    "- Include which role/function should own it (match one of the available member functions)\n"
    "- Have a clear, actionable title and a one-sentence description\n\n"
    "Be concrete and specific. Avoid vague tasks. Prefer tasks that produce a tangible output "
    "(doc, analysis, decision, meeting, deliverable, etc.).\n"
    'Return ONLY JSON, no fences: {"tasks": [{"department_function": "sales", "title": "..."}, '
    '"description": "...", "linked_kr_index": 0, "suggested_role": "sales"}]}'
)

# LLM prompt for proof-of-work review
TASK_REVIEW_SYSTEM = (
    "You are a task reviewer. Given a task description and the proof files a team member uploaded, "
    "determine if the task is genuinely complete.\n\n"
    "Rules:\n"
    "- Be fair but rigorous. A task is 'done' only if the evidence shows real completion.\n"
    "- If the proof is weak or ambiguous, flag it with notes on what's missing.\n"
    "- Confidence < 0.8 means 'needs human review'.\n"
    "Return ONLY JSON: {\"approved\": bool, \"confidence\": 0.0-1.0, \"notes\": \"...\"}"
)

# LLM prompt for task stage detection
TASK_STAGE_SYSTEM = (
    "You are a task stage detector. Given a task description, its current status, and the member's "
    "recent chat messages, determine what stage the task is at.\n\n"
    "Stages: not_started, researching, in_progress, almost_done, complete\n\n"
    "Return ONLY JSON: {\"stage\": \"...\", \"confidence\": 0.0-1.0}"
)

# Ch.44: Verification confidence thresholds by impact level
VERIFICATION_THRESHOLDS = {
    "low": 0.3,       # self-report sufficient
    "medium": 0.6,    # AI review required
    "high": 0.8,      # system evidence required
    "critical": 0.95, # external verification required
}


# Payload for weekly task generation
class TaskGenerateIn(BaseModel):
    week_start: Optional[str] = None


# Payload for task status updates
class TaskUpdateIn(BaseModel):
    status: Optional[str] = None
    proof_files: Optional[list[dict]] = None
    assigned_to: Optional[str] = None
    due_at: Optional[str] = None


# Compute the coming Monday's date
def _get_next_monday() -> datetime:
    today = now_utc()
    days_ahead = (7 - today.weekday()) % 7
    if days_ahead == 0:
        days_ahead = 7
    return (today + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)


# Pick best-fit member for a function
def _best_member_for_function(org_id: str, function: str) -> dict:
    members = list(members_col.find({"org_id": org_id, "status": "active"}))
    exact = [m for m in members if users_col.find_one({"id": m["user_id"]}, {"_id": 0, "function": 1}).get("function") == function]
    if exact:
        u = users_col.find_one({"id": exact[0]["user_id"]}, {"_id": 0, "name": 1})
        return {"user_id": exact[0]["user_id"], "name": (u or {}).get("name", "Member")}
    for m in members:
        u = users_col.find_one({"id": m["user_id"]}, {"_id": 0, "name": 1})
        if u:
            return {"user_id": m["user_id"], "name": u.get("name", "Member")}
    return {"user_id": "", "name": "Unassigned"}


@router.post("/tasks/generate-week")
def generate_weekly_tasks(body: TaskGenerateIn, user: dict = Depends(current_user)):
    """Owner-only. AI generates next week's tasks from the active quarterly plan. Runs Saturday night."""
    m = _require_owner(user)
    org_id = m["org_id"]
    plan = plans_col.find_one({"org_id": org_id, "status": "active"})
    if not plan:
        raise HTTPException(400, "No active plan. Ratify a plan first.")

    week_start = body.week_start or _get_next_monday().isoformat()

    org = orgs_col.find_one({"id": org_id})
    north_star = (org or {}).get("north_star", "") or "(not set)"

    members = list(members_col.find({"org_id": org_id, "status": "active"}))
    member_list = []
    for mm in members:
        u = users_col.find_one({"id": mm["user_id"]}, {"_id": 0, "name": 1, "function": 1})
        member_list.append({"name": (u or {}).get("name", "Member"), "function": (u or {}).get("function", "general")})

    dept_text = "\n".join(
        f"- {d['function']}: {d['objective']}\n  KRs: {'; '.join(d.get('key_results', [])[:4])}"
        for d in plan.get("departments", [])
    ) if plan.get("departments") else "(no departments)"
    member_text = "\n".join(f"- {m['name']} ({m['function']})" for m in member_list) or "(no members)"

    prompt = (
        f"FOUNDER'S VISION (North Star): {north_star}\n\n"
        f"COMPANY QUARTERLY OBJECTIVE: {plan.get('company_objective', '')}\n\n"
        f"DEPARTMENTS:\n{dept_text}\n\n"
        f"AVAILABLE MEMBERS:\n{member_text}\n\n"
        f"Generate 3-7 weekly tasks for each department for the week starting {week_start}. "
        f"Every task must trace back to the founder's vision."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=2000,
            system=[{"type": "text", "text": TASK_GENERATION_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"task generation failed: {e}")
        raise HTTPException(502, "Could not generate tasks. Try again.")

    tasks = []
    week_start_dt = datetime.fromisoformat(week_start)
    for t in (data.get("tasks") or [])[:30]:
        if not isinstance(t, dict) or not t.get("title"):
            continue
        func = norm_dep_function(t.get("department_function", "general"))
        best = _best_member_for_function(org_id, func)
        dept = next((d for d in (plan.get("departments") or []) if d.get("function") == func), {})
        kr_text = ((dept.get("key_results") or [])[int(t.get("linked_kr_index", 0))] if dept.get("key_results") else "")
        task = {
            "id": str(uuid.uuid4()),
            "org_id": org_id,
            "plan_id": plan["id"],
            "department_function": func,
            "linked_kr_index": int(t.get("linked_kr_index", 0)),
            "title": str(t.get("title", ""))[:200],
            "description": str(t.get("description", ""))[:1000],
            "founder_context": (
                f"Vision: {north_star}\n"
                f"→ Company objective: {plan.get('company_objective', '')}\n"
                f"→ {func}: {dept.get('objective', '')}\n"
                f"→ KR: {kr_text}"
            ),
            "assigned_to": best["user_id"],
            "assigned_to_name": best["name"],
            "status": "pending",
            "due_at": (week_start_dt + timedelta(days=6, hours=23, minutes=59)).isoformat(),
            "week_start": week_start,
            "generated_week": week_start_dt.isocalendar()[1],
            "proof_files": [],
            "ai_review": {"status": "pending", "notes": "", "confidence": 0.0, "reviewed_at": None},
            "stage": {"label": "not_started", "confidence": 1.0, "last_updated": now_utc().isoformat()},
            "escalation": {"dept_head_contacted": False, "dept_head_response": "",
                           "founder_contacted": False, "founder_response": "", "escalated_at": None},
            "created_at": now_utc().isoformat(),
            "updated_at": now_utc().isoformat(),
            "completed_at": None,
            "mission_version": plan.get("mission_version", 0),  # Ch.33: traceability
        }
        tasks.append(task)

    if tasks:
        tasks_col.insert_many(tasks)

    return {"tasks_generated": len(tasks), "week_start": week_start}


@router.get("/tasks")
def list_tasks(department_function: Optional[str] = None, status: Optional[str] = None,
               week_start: Optional[str] = None, assigned_to: Optional[str] = None,
               user: dict = Depends(current_user)):
    """Owner-only. List all tasks with filters."""
    m = _require_owner(user)
    q = {"org_id": m["org_id"]}
    if department_function:
        q["department_function"] = department_function
    if status:
        q["status"] = status
    if week_start:
        q["week_start"] = week_start
    if assigned_to:
        q["assigned_to"] = assigned_to

    rows = list(tasks_col.find(q, {"_id": 0}).sort("created_at", -1).limit(100))
    return {"tasks": rows, "count": len(rows)}


@router.get("/tasks/mine")
def my_tasks(user: dict = Depends(current_user)):
    """Member-only. Current user's active assigned tasks."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not part of an organization")
    q = {"org_id": m["org_id"], "assigned_to": user["id"],
         "status": {"$in": ["pending", "in_progress", "awaiting_review"]}}
    rows = list(tasks_col.find(q, {"_id": 0}).sort("due_at", 1).limit(50))
    return {"tasks": rows, "count": len(rows)}


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, body: TaskUpdateIn, user: dict = Depends(current_user)):
    """Member or owner update task status / proof files."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    task = tasks_col.find_one({"id": task_id, "org_id": m["org_id"]})
    if not task:
        raise HTTPException(404, "Task not found")
    if m["role"] != "owner" and task["assigned_to"] != user["id"]:
        raise HTTPException(403, "Can only update your own tasks")

    update = {"updated_at": now_utc().isoformat()}
    if body.status:
        update["status"] = body.status
        if body.status == "done":
            update["completed_at"] = now_utc().isoformat()
    if body.proof_files is not None:
        update["proof_files"] = body.proof_files
        update["status"] = "awaiting_review"
    if body.assigned_to and m["role"] == "owner":
        update["assigned_to"] = body.assigned_to
        u = users_col.find_one({"id": body.assigned_to}, {"_id": 0, "name": 1})
        update["assigned_to_name"] = (u or {}).get("name", "Member")
    if body.due_at and m["role"] == "owner":
        update["due_at"] = body.due_at

    tasks_col.update_one({"id": task_id}, {"$set": update})
    updated = tasks_col.find_one({"id": task_id}, {"_id": 0})

    if update.get("status") == "awaiting_review":
        try:
            _review_task_proof(task_id)
        except Exception as e:
            log.error(f"auto-review failed for {task_id}: {e}")

    return {"task": updated}


@router.post("/tasks/{task_id}/ai-review")
def review_task_proof(task_id: str, user: dict = Depends(current_user)):
    """Owner/system. AI reviews proof of work."""
    _require_owner(user)
    return _review_task_proof(task_id)


def _review_task_proof(task_id: str) -> dict:
    """Ch.44: Layered verification. Task completion is verified at increasing confidence
    thresholds based on impact: low (0.3, self-report), medium (0.6, AI review),
    high (0.8, system evidence), critical (0.95, external)."""
    task = tasks_col.find_one({"id": task_id})
    if not task:
        raise HTTPException(404, "Task not found")

    proof = task.get("proof_files") or []
    impact = task.get("impact", "medium")
    threshold = VERIFICATION_THRESHOLDS.get(impact, 0.6)

    if not proof:
        confidence = 0.3  # self-report only
        approved = confidence >= threshold
        return {"approved": approved, "confidence": confidence,
                "method": "self_report", "threshold": threshold,
                "notes": "No proof files — trusting member self-report" if approved
                         else f"Proof required (threshold {threshold})",
                "auto_completed": False}

    prompt = (
        f"TASK: {task['title']}\n"
        f"DESCRIPTION: {task['description']}\n"
        f"FILES UPLOADED: {json.dumps([{'name': f.get('name'), 'type': f.get('type')} for f in proof], indent=2)}\n\n"
        f"Based on the task description and the proof files submitted, determine if this task is genuinely complete."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=800,
            system=[{"type": "text", "text": TASK_REVIEW_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"task review failed for {task_id}: {e}")
        return {"approved": False, "confidence": 0, "notes": f"Review error: {e}", "auto_completed": False}

    approved = bool(data.get("approved", False))
    confidence = float(data.get("confidence", 0))
    notes = str(data.get("notes", ""))
    # Ch.44: gated by impact threshold
    method = "ai_review"
    if confidence < threshold:
        approved = False
        notes = f"[Verification threshold {threshold}] {notes}"
    auto_completed = approved and confidence >= threshold

    update = {
        "ai_review.status": "approved" if approved else "flagged",
        "ai_review.notes": notes,
        "ai_review.confidence": confidence,
        "ai_review.reviewed_at": now_utc().isoformat(),
        "updated_at": now_utc().isoformat(),
    }
    if auto_completed:
        update["status"] = "done"
        update["completed_at"] = now_utc().isoformat()

    tasks_col.update_one({"id": task_id}, {"$set": update})
    return {"approved": approved, "confidence": confidence, "notes": notes,
            "method": method, "threshold": threshold, "auto_completed": auto_completed}


@router.post("/tasks/{task_id}/stage")
def detect_task_stage(task_id: str, user: dict = Depends(current_user)):
    """AI detects task stage from member chat context."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    task = tasks_col.find_one({"id": task_id, "org_id": m["org_id"]})
    if not task:
        raise HTTPException(404, "Task not found")

    thread = threads_col.find_one({"user_id": task["assigned_to"]}, sort=[("last_turn_at", -1)])
    context = []
    if thread:
        for msg in (thread.get("messages") or [])[-10:]:
            context.append(f"[{msg['role']}]: {msg['text'][:200]}")
    chat_context = "\n".join(context[-6:]) or "(no recent chat)"

    prompt = (
        f"TASK: {task['title']}\n"
        f"DESCRIPTION: {task['description']}\n"
        f"CURRENT STATUS: {task['status']}\n"
        f"STAGE: {task.get('stage', {}).get('label', 'unknown')}\n"
        f"MEMBER'S RECENT CHAT:\n{chat_context}\n\n"
        f"What stage is this task at now?"
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=500,
            system=[{"type": "text", "text": TASK_STAGE_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"stage detection failed for {task_id}: {e}")
        return {"stage": task.get("stage", {}).get("label", "unknown"), "error": str(e)}

    label = str(data.get("stage", "not_started"))
    confidence = float(data.get("confidence", 0.5))
    tasks_col.update_one({"id": task_id}, {"$set": {
        "stage.label": label, "stage.confidence": confidence,
        "stage.last_updated": now_utc().isoformat(), "updated_at": now_utc().isoformat()}})
    return {"stage": label, "confidence": confidence}


@router.get("/tasks/weekly-digest")
def weekly_task_digest(user: dict = Depends(current_user)):
    """Owner-only. Weekly task aggregation for the cockpit."""
    m = _require_owner(user)
    org_id = m["org_id"]
    now = now_utc()
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = monday.isoformat()
    now_iso = now.isoformat()

    all_tasks = list(tasks_col.find({"org_id": org_id, "week_start": week_start}, {"_id": 0}).sort("created_at", 1))

    dept_map = {}
    member_map = {}
    flagged = []

    for t in all_tasks:
        func = t.get("department_function", "general")
        d = dept_map.setdefault(func, {"function": func, "total": 0, "done": 0, "overdue": 0,
                                        "pending": 0, "in_progress": 0, "flagged": 0})
        d["total"] += 1
        s = t.get("status", "pending")
        if s == "done":
            d["done"] += 1
        elif t.get("due_at", "") < now_iso and s != "done":
            d["overdue"] += 1
        if s == "pending":
            d["pending"] += 1
        if s == "in_progress":
            d["in_progress"] += 1
        if t.get("ai_review", {}).get("status") == "flagged":
            d["flagged"] += 1

        uid = t.get("assigned_to", "")
        mm = member_map.setdefault(uid, {"user_id": uid, "name": t.get("assigned_to_name", "Member"),
                                          "total": 0, "done": 0, "overdue": 0, "pending": 0})
        mm["total"] += 1
        if s == "done":
            mm["done"] += 1
        elif t.get("due_at", "") < now_iso and s != "done":
            mm["overdue"] += 1
        if s == "pending":
            mm["pending"] += 1

        if t.get("ai_review", {}).get("status") == "flagged" or s == "needs_clarification":
            flagged.append(t)

    return {
        "week_start": week_start,
        "total_tasks": len(all_tasks),
        "done": sum(1 for t in all_tasks if t.get("status") == "done"),
        "overdue": sum(1 for t in all_tasks if t.get("due_at", "") < now_iso and t.get("status") != "done"),
        "pending": sum(1 for t in all_tasks if t.get("status") == "pending"),
        "in_progress": sum(1 for t in all_tasks if t.get("status") == "in_progress"),
        "by_department": list(dept_map.values()),
        "by_member": list(member_map.values()),
        "flagged": flagged[:10],
    }


# ----------------------------------------------------------------- department head detection
@router.get("/department-heads")
def get_department_heads(user: dict = Depends(current_user)):
    """Owner-only. Auto-detect department heads from member activity."""
    m = _require_owner(user)
    org_id = m["org_id"]
    org = orgs_col.find_one({"id": org_id})
    existing = org.get("department_heads") or {}

    members = list(members_col.find({"org_id": org_id, "status": "active"}))
    rows = list(decisions_col.find({"org_id": org_id}, {"_id": 0, "function": 1, "user_id": 1, "status": 1}))

    by_func = {}
    for r in rows:
        f = r.get("function") or "general"
        if f not in by_func:
            by_func[f] = {}
        uid = r["user_id"]
        by_func[f][uid] = by_func[f].get(uid, 0) + 1

    heads = {}
    for func, uid_counts in by_func.items():
        if not uid_counts:
            continue
        top_uid = max(uid_counts, key=uid_counts.get)
        u = users_col.find_one({"id": top_uid}, {"_id": 0, "name": 1})
        heads[func] = {"user_id": top_uid, "name": (u or {}).get("name", "Member")}

    orgs_col.update_one({"id": org_id}, {"$set": {"department_heads": heads}})
    return {"detected": heads, "custom": existing}


@router.put("/department-heads")
def set_department_head(body: dict, user: dict = Depends(current_user)):
    """Owner-only. Manually set a department head."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    current = dict(org.get("department_heads") or {})
    for func, uid in body.items():
        if func in DEP_FUNCTIONS and uid:
            u = users_col.find_one({"id": uid}, {"_id": 0, "name": 1})
            current[func] = {"user_id": uid, "name": (u or {}).get("name", "Member")}
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {"department_heads": current}})
    return {"department_heads": current}


# ----------------------------------------------------------------- Ch.37: Risk Planning
class RiskIn(BaseModel):
    description: str = Field(min_length=2, max_length=500)
    likelihood: str = Field(default="medium")   # low | medium | high
    impact: str = Field(default="medium")        # low | medium | high
    mitigation: str = Field(default="", max_length=800)
    owner_name: str = Field(default="")


@router.get("/plan/risks")
def get_plan_risks(user: dict = Depends(current_user)):
    """Owner-only. Risk register for the active plan."""
    m = _require_owner(user)
    plan = plans_col.find_one({"org_id": m["org_id"], "status": "active"})
    if not plan:
        return {"risks": [], "count": 0, "note": "No active plan. Ratify a plan first."}
    risks = plan.get("risks", []) or []
    return {"risks": risks, "count": len(risks),
            "high_count": sum(1 for r in risks if r.get("likelihood") == "high" or r.get("impact") == "high")}


@router.post("/plan/risks")
def add_plan_risk(body: RiskIn, user: dict = Depends(current_user)):
    """Owner-only. Add a risk to the active plan's register."""
    m = _require_owner(user)
    plan = plans_col.find_one({"org_id": m["org_id"], "status": "active"})
    if not plan:
        raise HTTPException(400, "No active plan. Ratify a plan first.")
    risk = {
        "id": str(uuid.uuid4()),
        "description": body.description.strip(),
        "likelihood": body.likelihood if body.likelihood in ("low", "medium", "high") else "medium",
        "impact": body.impact if body.impact in ("low", "medium", "high") else "medium",
        "mitigation": body.mitigation.strip(),
        "owner_name": body.owner_name.strip(),
        "status": "active",
        "created_at": now_utc().isoformat(),
        "created_by": user["id"],
    }
    plans_col.update_one({"id": plan["id"]}, {"$push": {"risks": risk}})
    return {"risk": risk}


@router.delete("/plan/risks/{risk_id}")
def remove_plan_risk(risk_id: str, user: dict = Depends(current_user)):
    """Owner-only. Remove a risk from the register."""
    m = _require_owner(user)
    plan = plans_col.find_one({"org_id": m["org_id"], "status": "active"})
    if not plan:
        raise HTTPException(404, "No active plan found")
    plans_col.update_one({"id": plan["id"]}, {"$pull": {"risks": {"id": risk_id}}})
    return {"ok": True, "risk_id": risk_id}


# ----------------------------------------------------------------- Ch.33: Mission Traceability
@router.get("/mission/trace")
def mission_trace(user: dict = Depends(current_user)):
    """Owner-only. Checks what in the org traces back to the current mission.
    Returns orphans (items not linked to mission) and coverage %."""
    m = _require_owner(user)
    org_id = m["org_id"]
    org = orgs_col.find_one({"id": org_id})
    if not org:
        raise HTTPException(404, "Organization not found")
    current_version = org.get("strategy_version", 0)
    north_star = (org.get("north_star") or "").strip()

    # Active plans
    plans = list(plans_col.find({"org_id": org_id, "status": "active"}))
    # Active goal threads (check mission_version stamp)
    goal_threads = list(threads_col.find({"user_id": {"$in": [m["user_id"] for m in
                        list(members_col.find({"org_id": org_id, "status": "active"}))]}}))
    # Active tasks
    tasks = list(tasks_col.find({"org_id": org_id, "status": {"$nin": ["done", "dropped"]}}))

    orphans = []
    traced_count = 0
    total_items = 0

    for t in goal_threads:
        total_items += 1
        tv = t.get("mission_version")
        if tv is None or tv < current_version:
            orphans.append({"type": "goal_thread", "id": t.get("thread_id", ""),
                           "title": t.get("goal", "")[:100], "mission_version": tv,
                           "issue": "No mission trace" if tv is None else "Stale mission version"})
        else:
            traced_count += 1

    for t in tasks:
        total_items += 1
        tv = t.get("mission_version")
        if tv is None or tv < current_version:
            orphans.append({"type": "task", "id": t.get("id", ""),
                           "title": t.get("title", "")[:100], "mission_version": tv,
                           "issue": "No mission trace" if tv is None else "Stale mission version"})
        else:
            traced_count += 1

    for p in plans:
        total_items += 1
        tv = p.get("mission_version")
        if tv is None or tv < current_version:
            orphans.append({"type": "plan", "id": p.get("id", ""),
                           "title": p.get("target", "")[:100], "mission_version": tv,
                           "issue": "No mission trace" if tv is None else "Stale mission version"})
        else:
            traced_count += 1

    coverage_pct = round(100 * traced_count / total_items) if total_items > 0 else 100
    return {
        "north_star": north_star,
        "strategy_version": current_version,
        "total_items": total_items,
        "traced": traced_count,
        "orphans": orphans[:20],
        "coverage_pct": coverage_pct,
        "status": "healthy" if coverage_pct >= 80 else ("needs_attention" if coverage_pct >= 50 else "drift_detected"),
    }


# ================================================================= Ch.19: Organization Engine
ORG_GEN_SYSTEM = """You design executive organizations that achieve missions. Given a company's mission,
stage, team size, and industry, generate the organization structure that best serves the mission.

Principles:
- Structure follows strategy. Every division must trace back to the mission.
- Lean by default. Start with minimum viable organization for the company stage.
- Stage-appropriate: startup (3-5 departments), growth (5-10), enterprise (10-20+).
- Each department has: function, purpose, objective, 2-3 measurable KPIs.
- Reporting structure: clear hierarchy, one head per department.

Return ONLY JSON:
{"divisions": [{
    "name": "Division name",
    "purpose": "Why this division exists (trace to mission)",
    "budget_pct": 30,
    "departments": [{
        "function": "sales|marketing|product|engineering|operations|finance|leadership",
        "objective": "One line objective for this quarter",
        "kpis": ["measurable KPI 1", "measurable KPI 2"],
        "headcount_recommendation": 2,
        "budget_pct_of_division": 50
    }]
}],
"reporting_structure": "Brief description of reporting lines",
"spans_and_layers": "How many layers and typical span of control",
"key_hires_needed": ["role 1", "role 2"],
"risks_in_this_structure": ["risk 1", "risk 2"],
"stage_rationale": "Why this structure fits their current stage"
}"""


def validate_org_structure(structure: dict, stage: str) -> list:
    """Ch.19: Deterministic validation before presenting to founder. Returns list of issues."""
    issues = []
    if not structure:
        return ["Empty structure"]
    divisions = structure.get("divisions") or []
    if not divisions:
        issues.append("No divisions generated")

    total_budget = 0
    all_dept_funcs = set()
    valid_funcs = {"sales", "marketing", "product", "engineering", "operations", "finance", "leadership", "general"}

    for div in divisions:
        total_budget += div.get("budget_pct", 0)
        depts = div.get("departments") or []
        if not depts:
            issues.append(f"Division '{div.get('name', '?')}' has no departments")
        for d in depts:
            func = d.get("function", "").lower()
            if func and func not in valid_funcs:
                issues.append(f"Unknown function '{func}' in {div.get('name', '?')}")
            if func in all_dept_funcs:
                issues.append(f"Duplicate function '{func}' across divisions")
            all_dept_funcs.add(func)

    if abs(total_budget - 100) > 2:
        issues.append(f"Division budgets sum to {total_budget}%, not 100%")

    if stage == "startup" and len(divisions) > 3:
        issues.append(f"Generated {len(divisions)} divisions for a startup (max recommended: 3)")

    return issues


def generate_org_structure(north_star: str, stage: str, team_size: int, industry: str = "",
                            priorities: list = None, members_text: str = "") -> dict:
    """Ch.19: One LLM call. Transform mission into a complete org structure."""
    prompt = (
        f"MISSION (North Star): {north_star}\n"
        f"COMPANY STAGE: {stage}\n"
        f"TEAM SIZE: {team_size}\n"
        + (f"INDUSTRY: {industry}\n" if industry else "")
        + (f"STRATEGIC PRIORITIES: {'; '.join(priorities)}\n" if priorities else "")
        + (f"AVAILABLE MEMBERS:\n{members_text}\n" if members_text else "")
        + f"\nGenerate the organization structure that best serves this mission at their current stage."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=2000,
            system=[{"type": "text", "text": ORG_GEN_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        structure = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"org generation failed: {e}")
        raise HTTPException(502, "Could not generate organization structure. Try again.")

    issues = validate_org_structure(structure, stage)
    return {"structure": structure, "issues": issues, "ready": len(issues) == 0}


@router.get("/structure")
def get_org_structure(user: dict = Depends(current_user)):
    """Owner-only. View current org structure (generated or custom)."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    structure = org.get("organization") or {}
    return {
        "active": bool(structure.get("approved_at")),
        "structure": structure,
        "north_star": org.get("north_star", ""),
    }


# Payload for org structure generation
class GenerateOrgIn(BaseModel):
    stage: str = Field(default="startup")  # startup | growth | enterprise
    team_size: int = Field(default=5, ge=1, le=10000)
    industry: str = Field(default="", max_length=100)


@router.post("/structure/generate")
def generate_structure(body: GenerateOrgIn, user: dict = Depends(current_user)):
    """Owner-only. AI generates org structure from the North Star. Founder reviews before activation."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    north_star = (org.get("north_star") or "").strip()
    if not north_star:
        raise HTTPException(400, "Set your North Star first (Strategy page)")
    priorities = org.get("priorities") or []
    members = list(members_col.find({"org_id": m["org_id"], "status": "active"}))
    member_text = "\n".join(
        f"- {(users_col.find_one({'id': mm['user_id']}, {'_id': 0, 'name': 1, 'function': 1}) or {}).get('name', 'Member')}"
        f" ({(users_col.find_one({'id': mm['user_id']}, {'_id': 0, 'function': 1}) or {}).get('function', 'general')})"
        for mm in members) or "(no members)"

    result = generate_org_structure(north_star, body.stage, body.team_size, body.industry,
                                     priorities, member_text)

    # Store as draft (not yet activated)
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {
        "organization_draft": {
            "structure": result["structure"],
            "generated_at": now_utc().isoformat(),
            "stage": body.stage,
            "team_size": body.team_size,
        },
    }})
    return result


@router.post("/structure/activate")
def activate_structure(user: dict = Depends(current_user)):
    """Owner-only. Human ratification gate: the generated org goes live only when approved."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    draft = org.get("organization_draft") or {}
    if not draft.get("structure"):
        raise HTTPException(400, "Generate an organization structure first")
    orgs_col.update_one({"id": m["org_id"]}, {"$set": {
        "organization": {**draft["structure"], "approved_at": now_utc().isoformat(),
                         "version": (org.get("organization") or {}).get("version", 0) + 1},
        "organization_draft": None,
    }})
    return {"ok": True, "message": "Organization structure activated"}


# ================================================================= Ch.20-21: Executive Org Architecture + Division Generator
# ponytail: Ch.20 (architecture) and Ch.21 (division generator) are merged — the structure
# generation above already produces divisions, departments, KPIs, and reporting lines.
# Ch.20-21 are satisfied by the Ch.19 endpoint + the per-department view below.

@router.get("/structure/departments")
def list_departments(user: dict = Depends(current_user)):
    """Owner-only. Flattened view of all departments across divisions."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    structure = (org or {}).get("organization") or {}
    divisions = structure.get("divisions") or []
    depts = []
    for div in divisions:
        for d in (div.get("departments") or []):
            depts.append({
                "function": d.get("function", "general"),
                "objective": d.get("objective", ""),
                "kpis": d.get("kpis", []),
                "division": div.get("name", ""),
                "budget_pct": d.get("budget_pct_of_division", 0),
                "headcount": d.get("headcount_recommendation", 1),
            })
    return {"departments": depts, "count": len(depts),
            "active": bool(structure.get("approved_at"))}


# ================================================================= Ch.24: Internal Economy Engine
ECONOMY_SYSTEM = """You are SALAAR's resource allocation function. Given resource requests from departments,
allocate the available budget based on: strategic alignment (40%), past ROI (30%), and risk of underfunding (30%).
Be explicit about trade-offs. Every denial comes with reasoning the department can learn from.
Return ONLY JSON:
{"allocations": [{"department_function": "sales", "allocated_inr": 50000, "approved": true,
                  "reasoning": "one line on why", "conditions": "what must be true for this to work"}]}"""


@router.get("/economy/requests")
def list_resource_requests(user: dict = Depends(current_user)):
    """Owner-only. All pending resource requests from departments."""
    m = _require_owner(user)
    rows = list(resource_requests_col.find(
        {"org_id": m["org_id"], "status": "submitted"},
        {"_id": 0}).sort("created_at", -1).limit(50))
    return {"requests": rows, "count": len(rows)}


@router.post("/economy/requests")
def submit_resource_request(body: dict, user: dict = Depends(current_user)):
    """Department head submits a resource request."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    now = now_utc()
    req = {
        "id": str(uuid.uuid4()),
        "org_id": m["org_id"],
        "executive_id": user["id"],
        "period_start": body.get("period_start", now.isoformat()),
        "period_end": body.get("period_end", ""),
        "department_function": body.get("department_function", "general"),
        "requested_budget_inr": int(body.get("requested_budget_inr", 0)),
        "requested_headcount": int(body.get("requested_headcount", 0)),
        "justification": str(body.get("justification", ""))[:800],
        "expected_outcomes": body.get("expected_outcomes", []),
        "status": "submitted",
        "allocated_budget_inr": 0,
        "salaar_reasoning": "",
        "founder_modified": False,
        "created_at": now.isoformat(),
    }
    resource_requests_col.insert_one(req)
    return {"request": req}


@router.post("/economy/allocate")
def allocate_resources(user: dict = Depends(current_user)):
    """Owner-only. SALAAR evaluates pending requests and produces an allocation proposal.
    Founder reviews and approves before it takes effect."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")

    requests = list(resource_requests_col.find({"org_id": m["org_id"], "status": "submitted"}))
    if not requests:
        return {"allocations": [], "note": "No pending resource requests"}

    north_star = (org.get("north_star") or "").strip()
    priorities = org.get("priorities") or []
    total_budget_hint = int(org.get("total_budget_inr", 0) or 0)

    # Build context for SALAAR
    req_text = "\n".join(
        f"- {r['department_function']}: requests Rs{r['requested_budget_inr']}, "
        f"{r['requested_headcount']} headcount. Justification: {r['justification'][:200]}"
        for r in requests[:20])

    # Include past performance data per department
    perf_lines = []
    for func in set(r["department_function"] for r in requests):
        dept_rows = list(decisions_col.find(
            {"org_id": m["org_id"], "function": func,
             "outcome.status": {"$in": ["success", "partial", "failed"]}},
            {"_id": 0, "outcome": 1}))
        if dept_rows:
            succ = sum(1 for d in dept_rows if d["outcome"]["status"] == "success")
            part = sum(1 for d in dept_rows if d["outcome"]["status"] == "partial")
            roi = round(100 * (succ + 0.5 * part) / len(dept_rows)) if dept_rows else None
            perf_lines.append(f"- {func}: {len(dept_rows)} decisions, {roi}% effectiveness")

    prompt = (
        f"NORTH STAR: {north_star}\n"
        f"PRIORITIES: {'; '.join(priorities)}\n"
        f"TOTAL BUDGET: Rs{total_budget_hint}\n\n"
        f"PAST PERFORMANCE:\n{chr(10).join(perf_lines) if perf_lines else '(no data)'}\n\n"
        f"RESOURCE REQUESTS:\n{req_text}\n\n"
        f"Allocate budget to departments. Score each on: alignment to North Star (40%), "
        f"past ROI (30%), risk of underfunding (30%). Deny what you must, explain every denial. "
        f"Total allocated must not exceed total budget."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1500,
            system=[{"type": "text", "text": ECONOMY_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        allocations = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"economy allocation failed: {e}")
        raise HTTPException(502, "Could not allocate resources. Try again.")

    allocated = allocations.get("allocations", [])
    for alloc in allocated:
        func = alloc.get("department_function", "")
        if func:
            resource_requests_col.update_many(
                {"org_id": m["org_id"], "department_function": func, "status": "submitted"},
                {"$set": {"status": "approved", "allocated_budget_inr": alloc.get("allocated_inr", 0),
                          "salaar_reasoning": alloc.get("reasoning", ""),
                          "resolved_at": now_utc().isoformat()}})

    return {"allocations": allocated, "note": "Founder must approve allocations before funds are released."}


# ================================================================= Ch.26: Organization Memory
@router.get("/memory")
def list_org_memory(domain: Optional[str] = None, knowledge_type: Optional[str] = None,
                     limit: int = 20, user: dict = Depends(current_user)):
    """Owner-only. What the organization has learned — patterns, lessons, processes.
    Feeds from Autopsy Engine (Ch.18) and executive archival (Ch.30)."""
    m = _require_owner(user)
    q = {"org_id": m["org_id"]}
    if domain:
        q["domain"] = domain
    if knowledge_type:
        q["knowledge_type"] = knowledge_type

    rows = list(org_memory_col.find(q, {"_id": 0}).sort("created_at", -1).limit(limit))
    domains = org_memory_col.distinct("domain", {"org_id": m["org_id"]})
    types = org_memory_col.distinct("knowledge_type", {"org_id": m["org_id"]})

    return {
        "memories": rows,
        "count": len(rows),
        "domains": domains,
        "knowledge_types": types,
        "high_confidence": sum(1 for r in rows if r.get("confidence", 0) >= 0.7),
    }


@router.post("/memory")
def add_org_memory(body: dict, user: dict = Depends(current_user)):
    """Owner-only. Manually add a lesson or pattern to organization memory."""
    m = _require_owner(user)
    mem = {
        "id": str(uuid.uuid4()),
        "org_id": m["org_id"],
        "domain": body.get("domain", "general"),
        "topic": body.get("topic", ""),
        "knowledge_type": body.get("knowledge_type", "lesson"),
        "content": {
            "summary": str(body.get("summary", ""))[:500],
            "detail": str(body.get("detail", ""))[:1000],
            "evidence": str(body.get("evidence", ""))[:500],
            "counter_evidence": str(body.get("counter_evidence", ""))[:500],
        },
        "confidence": float(body.get("confidence", 0.5)),
        "observation_count": int(body.get("observation_count", 1)),
        "source": [{"type": "manual", "id": user["id"], "timestamp": now_utc().isoformat()}],
        "tags": body.get("tags", []),
        "created_at": now_utc().isoformat(),
    }
    org_memory_col.insert_one(mem)
    return {"memory": mem}


@router.get("/memory/search")
def search_org_memory(query: str = "", limit: int = 10, user: dict = Depends(current_user)):
    """Owner-only. Full-text search across organization memory."""
    m = _require_owner(user)
    if not query.strip():
        return {"memories": [], "count": 0}

    q = {"org_id": m["org_id"], "$text": {"$search": query.strip()}}
    try:
        rows = list(org_memory_col.find(q, {"_id": 0, "score": {"$meta": "textScore"}})
                    .sort([("score", {"$meta": "textScore"})]).limit(limit))
    except Exception:
        org_memory_col.create_index([("content.summary", "text"), ("content.detail", "text"),
                                     ("topic", "text"), ("tags", "text")])
        rows = list(org_memory_col.find(q, {"_id": 0, "score": {"$meta": "textScore"}})
                    .sort([("score", {"$meta": "textScore"})]).limit(limit))

    return {"memories": rows, "count": len(rows), "query": query}


# ================================================================= Ch.36: Project & Resource Planning
class ProjectIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    description: str = Field(default="", max_length=2000)
    department_function: str = Field(default="general")
    target_outcome: str = Field(default="", max_length=500)
    budget_inr: int = Field(default=0, ge=0)
    deadline: Optional[str] = None
    milestones: list[dict] = Field(default_factory=list)


@router.post("/projects")
def create_project(body: ProjectIn, user: dict = Depends(current_user)):
    """Owner-only. Create a project under a department."""
    m = _require_owner(user)
    func = norm_dep_function(body.department_function)
    now = now_utc()
    project = {
        "id": str(uuid.uuid4()),
        "org_id": m["org_id"],
        "name": body.name.strip(),
        "description": body.description.strip(),
        "department_function": func,
        "target_outcome": body.target_outcome.strip(),
        "budget_inr": body.budget_inr,
        "deadline": body.deadline,
        "milestones": [{"id": str(uuid.uuid4()), "title": str(ms.get("title", ""))[:200],
                         "status": "pending", "due_at": ms.get("due_at")}
                        for ms in body.milestones if isinstance(ms, dict) and ms.get("title")][:20],
        "status": "active",
        "created_at": now.isoformat(),
        "created_by": user["id"],
        "completed_at": None,
    }
    projects_col.insert_one(project)
    return {"project": project}


@router.get("/projects")
def list_projects(department_function: Optional[str] = None, status: Optional[str] = None,
                  user: dict = Depends(current_user)):
    """Owner-only. All projects with filters."""
    m = _require_owner(user)
    q = {"org_id": m["org_id"]}
    if department_function:
        q["department_function"] = department_function
    if status:
        q["status"] = status
    rows = list(projects_col.find(q, {"_id": 0}).sort("created_at", -1).limit(50))
    return {"projects": rows, "count": len(rows)}


@router.patch("/projects/{project_id}")
def update_project(project_id: str, body: dict, user: dict = Depends(current_user)):
    """Owner-only. Update project status or add milestones."""
    m = _require_owner(user)
    proj = projects_col.find_one({"id": project_id, "org_id": m["org_id"]})
    if not proj:
        raise HTTPException(404, "Project not found")
    upd = {}
    if body.get("status"):
        upd["status"] = body["status"]
        if body["status"] == "completed":
            upd["completed_at"] = now_utc().isoformat()
    if body.get("milestones"):
        upd["milestones"] = body["milestones"]
    if upd:
        projects_col.update_one({"id": project_id}, {"$set": upd})
    return {"ok": True, "project_id": project_id}


# ================================================================= Ch.38: Department Automation
class AutomationTemplateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    department_function: str = Field(default="general")
    description_template: str = Field(default="", max_length=1000)
    frequency: str = Field(default="weekly")   # daily | weekly | monthly
    day_of_week: int = Field(default=1, ge=0, le=6)       # 0=Monday
    assign_to_function: str = Field(default="general")
    auto_generate: bool = False


@router.post("/automation/templates")
def create_template(body: AutomationTemplateIn, user: dict = Depends(current_user)):
    """Owner-only. Define a recurring task template for a department."""
    m = _require_owner(user)
    template = {
        "id": str(uuid.uuid4()),
        "org_id": m["org_id"],
        "name": body.name.strip(),
        "department_function": norm_dep_function(body.department_function),
        "description_template": body.description_template.strip(),
        "frequency": body.frequency if body.frequency in ("daily", "weekly", "monthly") else "weekly",
        "day_of_week": body.day_of_week,
        "assign_to_function": norm_dep_function(body.assign_to_function),
        "auto_generate": body.auto_generate,
        "created_at": now_utc().isoformat(),
    }
    automation_templates_col.insert_one(template)
    return {"template": template}


@router.get("/automation/templates")
def list_templates(department_function: Optional[str] = None, user: dict = Depends(current_user)):
    """Owner-only. List recurring task templates."""
    m = _require_owner(user)
    q = {"org_id": m["org_id"]}
    if department_function:
        q["department_function"] = department_function
    rows = list(automation_templates_col.find(q, {"_id": 0}).sort("created_at", -1).limit(50))
    return {"templates": rows, "count": len(rows)}


# Remove a recurring task template
@router.delete("/automation/templates/{template_id}")
def delete_template(template_id: str, user: dict = Depends(current_user)):
    m = _require_owner(user)
    automation_templates_col.delete_one({"id": template_id, "org_id": m["org_id"]})
    return {"ok": True}


# ================================================================= Ch.41: Dependency Engine
class DependencyIn(BaseModel):
    depends_on_task_id: str = Field(min_length=1)


@router.post("/tasks/{task_id}/dependencies")
def add_task_dependency(task_id: str, body: DependencyIn, user: dict = Depends(current_user)):
    """Owner-only. Mark that this task depends on another task being completed first."""
    m = _require_owner(user)
    task = tasks_col.find_one({"id": task_id, "org_id": m["org_id"]})
    if not task:
        raise HTTPException(404, "Task not found")
    dep_task = tasks_col.find_one({"id": body.depends_on_task_id, "org_id": m["org_id"]})
    if not dep_task:
        raise HTTPException(404, "Dependency task not found")
    if task_id == body.depends_on_task_id:
        raise HTTPException(400, "A task cannot depend on itself")

    deps = task.get("dependencies") or []
    existing = [d for d in deps if d.get("task_id") == body.depends_on_task_id]
    if existing:
        return {"ok": True, "already_exists": True}

    deps.append({"task_id": body.depends_on_task_id, "added_at": now_utc().isoformat(),
                 "title": dep_task.get("title", "")[:100]})
    tasks_col.update_one({"id": task_id}, {"$set": {"dependencies": deps}})

    # Mark task as blocked if dependency is not done
    if dep_task["status"] != "done":
        tasks_col.update_one({"id": task_id}, {"$set": {"status": "blocked", "blocked_by": body.depends_on_task_id}})

    return {"ok": True, "dependencies": deps}


@router.get("/tasks/{task_id}/dependencies")
def get_task_dependencies(task_id: str, user: dict = Depends(current_user)):
    """View what this task depends on and what depends on it."""
    m = _require_owner(user)
    task = tasks_col.find_one({"id": task_id, "org_id": m["org_id"]})
    if not task:
        raise HTTPException(404, "Task not found")

    depends_on = task.get("dependencies") or []
    # Find tasks that depend on this one
    blocked_by_this = list(tasks_col.find(
        {"org_id": m["org_id"], "dependencies.task_id": task_id},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "assigned_to_name": 1}))

    # Check for circular dependencies
    visited = set()

    def has_circular(tid, path=None):
        if path is None:
            path = set()
        if tid in path:
            return True
        path.add(tid)
        t = tasks_col.find_one({"id": tid}, {"_id": 0, "dependencies": 1})
        for d in (t.get("dependencies") or []) if t else []:
            if has_circular(d["task_id"], path.copy()):
                return True
        return False

    circular = has_circular(task_id)

    return {
        "depends_on": depends_on,
        "blocked_by_this": blocked_by_this,
        "has_circular_dependency": circular,
    }


@router.post("/tasks/resolve-blockers")
def resolve_blockers(user: dict = Depends(current_user)):
    """Owner-only. Auto-resolve blocked tasks whose dependencies are now done."""
    m = _require_owner(user)
    blocked = list(tasks_col.find({"org_id": m["org_id"], "status": "blocked"}))
    resolved = 0
    for task in blocked:
        blocker_id = task.get("blocked_by")
        if blocker_id:
            blocker = tasks_col.find_one({"id": blocker_id})
            if blocker and blocker.get("status") == "done":
                tasks_col.update_one({"id": task["id"]}, {"$set": {"status": "pending", "blocked_by": None}})
                resolved += 1
    return {"resolved": resolved, "still_blocked": len(blocked) - resolved}


# ================================================================= Ch.43: Simulation Engine
SIMULATION_SYSTEM = """You are a company simulator. Given a proposed organizational change and the current
state of the company, project the likely outcomes across multiple scenarios.

Analyze second-order effects: if department X gets more budget, what happens to department Y?
If headcount changes, how does that cascade through dependencies?
Be honest about assumptions and uncertainty.

Return ONLY JSON:
{"best_case": {"outcome": "one line describing the best plausible outcome", "probability": 20,
               "key_assumptions": ["assumption that makes this happen"]},
 "most_likely": {"outcome": "one line describing the most likely outcome", "probability": 60,
                 "key_assumptions": ["assumption that drives this"]},
 "worst_case": {"outcome": "one line describing the worst plausible outcome", "probability": 20,
                "key_assumptions": ["assumption that causes this"]},
 "second_order_effects": ["unexpected ripple effect 1", "ripple effect 2"],
 "recommendation": "one line: ship, modify, or abandon this change"}"""


# Payload for what-if simulation
class SimulateIn(BaseModel):
    change_description: str = Field(min_length=5, max_length=1000)
    scenario_type: str = Field(default="reorg")  # reorg | budget | hiring | strategy


@router.post("/simulate")
def simulate_change(body: SimulateIn, user: dict = Depends(current_user)):
    """Owner-only. What-if simulation: project the effects of a proposed organizational change."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")

    structure = org.get("organization") or {}
    north_star = (org.get("north_star") or "").strip()

    # Gather current state for context
    dept_text = ""
    divisions = structure.get("divisions") or []
    for div in divisions:
        for d in (div.get("departments") or []):
            func = d.get("function", "general")
            perf = _effectiveness_by_function(m["org_id"])
            eff = next((p for p in perf if p["function"] == func), None)
            eff_pct = f"{eff.get('effectiveness_pct', '?')}%" if eff and eff.get("effectiveness_pct") is not None else "?"
            dept_text += f"- {func}: {d.get('objective', '')} (effectiveness: {eff_pct})\n"

    prompt = (
        f"COMPANY NORTH STAR: {north_star}\n\n"
        f"CURRENT STRUCTURE:\n{dept_text}\n"
        f"PROPOSED CHANGE: {body.change_description}\n"
        f"SCENARIO TYPE: {body.scenario_type}\n\n"
        f"Simulate this change. Project best/most-likely/worst case, find second-order effects, "
        f"and give a clear recommendation."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1200,
            system=[{"type": "text", "text": SIMULATION_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        result = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"simulation failed: {e}")
        raise HTTPException(502, "Could not run simulation. Try again.")

    return {
        "scenario": body.change_description,
        "simulation": result,
        "context": {"north_star": north_star, "departments": len(divisions)},
    }


# ================================================================= Ch.46: Recovery & Rollback
@router.post("/tasks/{task_id}/reopen")
def reopen_task(task_id: str, reason: str = "", user: dict = Depends(current_user)):
    """Owner-only. Reopen a failed or dropped task with a recovery plan."""
    m = _require_owner(user)
    task = tasks_col.find_one({"id": task_id, "org_id": m["org_id"]})
    if not task:
        raise HTTPException(404, "Task not found")
    if task["status"] not in ("done", "dropped", "failed"):
        raise HTTPException(400, f"Task is {task['status']}, not done/dropped/failed")

    upd = {
        "status": "pending",
        "reopened_at": now_utc().isoformat(),
        "reopen_reason": reason.strip() or "Recovery — reattempting",
        "completed_at": None,
        "ai_review": {"status": "pending", "notes": "", "confidence": 0.0, "reviewed_at": None},
    }
    tasks_col.update_one({"id": task_id}, {"$set": upd})

    # ponytail: record in org_memory so the org learns from the failure
    if org_memory_col is not None:
        org_memory_col.insert_one({
            "id": str(uuid.uuid4()),
            "org_id": m["org_id"],
            "domain": task.get("department_function", "general"),
            "topic": "task_recovery",
            "knowledge_type": "lesson",
            "content": {"summary": f"Task '{task.get('title','')}' reopened after {task['status']}",
                       "detail": reason.strip() or "No recovery reason provided",
                       "evidence": f"Status was {task['status']}", "counter_evidence": ""},
            "confidence": 0.5, "observation_count": 1,
            "source": [{"type": "recovery", "id": task_id, "timestamp": now_utc().isoformat()}],
            "tags": ["recovery", task.get("department_function", "general")],
            "created_at": now_utc().isoformat(),
        })

    return {"ok": True, "task_id": task_id, "status": "pending", "previous_status": task["status"]}


# ================================================================= Ch.47-49: Optimization, Health, Continuous Improvement
OPTIMIZATION_SYSTEM = """You are a weekly optimization engine. Analyze the organization's performance data
and produce: 3 things to AMPLIFY (what's working and should get more resources), 3 things to FIX (what's
broken and needs attention), and 1 thing to TRY (a bold experiment that could unlock step-change improvement).

Be specific and data-driven. Every recommendation must reference actual numbers from the data provided.
Return ONLY JSON:
{"amplify": [{"what": "one line", "evidence": "the data point", "expected_impact": "one line"}],
 "fix": [{"what": "one line", "evidence": "the data point", "how": "one line on the fix"}],
 "try": {"what": "one bold experiment", "rationale": "why it could work", "cost_to_test": "one line"},
 "overall_assessment": "one honest line on how the org is doing"}"""

# LLM prompt for org health diagnosis
HEALTH_SYSTEM = """You are an organization health diagnostician. Given department performance data,
diagnose the health of the organization along these dimensions and score each 0-100:
- Capacity: workload vs headcount per department
- Performance: KPI trends and success rates
- Communication: escalation rates and cross-department collaboration
- Budget: burn rate vs plan
- Alignment: activities traceable to mission
- Knowledge: concentration risk and gaps

Return ONLY JSON:
{"overall_score": 65, "dimensions": {"capacity": {"score": 70, "issues": []}, ...},
 "top_issues": [{"severity": "high|medium|low", "description": "...", "affected_department": "...", "recommendation": "..."}],
 "trend": "improving|stable|declining"}"""


@router.get("/optimization/weekly-brief")
def weekly_optimization_brief(user: dict = Depends(current_user)):
    """Owner-only. AI-generated weekly brief: what to amplify, fix, and try."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")

    # Gather data directly (ponytail: simpler than calling cockpit recursively)
    org_id = m["org_id"]
    perf = _effectiveness_by_function(org_id)

    perf_text = "\n".join(
        f"- {p['function']}: {p['decisions']} decisions, {p['avg_alignment']} avg alignment, "
        f"{p.get('effectiveness_pct', '?')}% effectiveness" for p in perf)

    prompt = (
        f"NORTH STAR: {org.get('north_star', '') or '(not set)'}\n"
        f"PERFORMANCE DATA:\n{perf_text}\n\n"
        f"Produce the weekly optimization brief."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1000,
            system=[{"type": "text", "text": OPTIMIZATION_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        brief = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"optimization brief failed: {e}")
        raise HTTPException(502, "Could not generate brief. Try again.")

    # Ch.49: Store for continuous improvement tracking
    brief["id"] = str(uuid.uuid4())
    brief["week_start"] = now_utc().isoformat()[:10]
    brief["created_at"] = now_utc().isoformat()
    # Track implementation later
    orgs_col.update_one({"id": m["org_id"]}, {"$push": {
        "optimization_briefs": {"$each": [brief], "$slice": -26}}
    })

    return brief


@router.get("/optimization/health")
def organization_health(user: dict = Depends(current_user)):
    """Owner-only. Weekly health diagnostic across all departments."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")

    perf = _effectiveness_by_function(m["org_id"])
    perf_text = "\n".join(
        f"- {p['function']}: {p['decisions']} decisions, {p['avg_alignment']} avg, "
        f"{p.get('effectiveness_pct', '?')}% effective" for p in perf)

    prompt = (
        f"NORTH STAR: {org.get('north_star', '') or '(not set)'}\n"
        f"DEPARTMENT PERFORMANCE:\n{perf_text}\n\n"
        f"Diagnose the org's health."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1000,
            system=[{"type": "text", "text": HEALTH_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        health = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"health check failed: {e}")
        raise HTTPException(502, "Could not run health check. Try again.")

    health["id"] = str(uuid.uuid4())
    health["week_start"] = now_utc().isoformat()[:10]
    health["created_at"] = now_utc().isoformat()
    orgs_col.update_one({"id": m["org_id"]}, {"$push": {
        "health_snapshots": {"$each": [health], "$slice": -52}}
    })
    return health


# ================================================================= Ch.50-52: Organization Evolution
EVOLUTION_SYSTEM = """You are an organization evolution advisor. Given the company's current structure,
performance data, and growth trajectory, propose structural changes that would improve outcome achievement.

Options: split an overgrown department, merge two underperforming ones, create a new division,
promote an executive, archive a role, or adjust reporting lines.

Every proposal must be: backed by evidence, have expected impact, and address a real problem.
Return ONLY JSON:
{"proposals": [{"type": "split|merge|create|archive|promote|restructure",
                "description": "one line on the change",
                "affected_entities": ["dept_or_exec"],
                "evidence": "the data justifying it",
                "expected_impact": "one line",
                "risks": ["risk of this change"],
                "priority": "high|medium|low"}]}"""


@router.get("/evolution/review")
def evolution_review(user: dict = Depends(current_user)):
    """Owner-only. Quarterly evolution review: structural change proposals backed by data."""
    m = _require_owner(user)
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")

    structure = org.get("organization") or {}
    perf = _effectiveness_by_function(m["org_id"])

    dept_text = ""
    divisions = structure.get("divisions") or []
    for div in divisions:
        for d in (div.get("departments") or []):
            func = d.get("function", "general")
            p = next((x for x in perf if x["function"] == func), {})
            dept_text += (
                f"- {func} (Division: {div.get('name','?')}): objective={d.get('objective','')[:100]}, "
                f"decisions={p.get('decisions',0)}, avg_align={p.get('avg_alignment','?')}, "
                f"effectiveness={p.get('effectiveness_pct','?')}%\n"
            )

    prompt = (
        f"NORTH STAR: {org.get('north_star', '') or '(not set)'}\n"
        f"STAGE: {(org.get('organization_draft') or {}).get('stage', 'startup')}\n"
        f"CURRENT STRUCTURE:\n{dept_text}\n"
        f"Propose structural changes that would improve outcome achievement."
    )

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1200,
            system=[{"type": "text", "text": EVOLUTION_SYSTEM}],
            messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        evolution = json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"evolution review failed: {e}")
        raise HTTPException(502, "Could not run evolution review. Try again.")

    evolution["quarter"] = f"Q{(now_utc().month-1)//3+1}-{now_utc().year}"
    evolution["reviewed_at"] = now_utc().isoformat()
    orgs_col.update_one({"id": m["org_id"]}, {"$push": {
        "evolution_proposals": {"$each": [evolution], "$slice": -12}}
    })

    # Ch.52: Institutional memory review — surface patterns from org_memory
    memories = list(org_memory_col.find(
        {"org_id": m["org_id"]},
        {"_id": 0, "domain": 1, "topic": 1, "content.summary": 1, "confidence": 1}
    ).sort("created_at", -1).limit(20)) if org_memory_col is not None else []

    return {
        "evolution": evolution,
        "institutional_memory_snapshot": {
            "total_memories": org_memory_col.count_documents({"org_id": m["org_id"]}) if org_memory_col is not None else 0,
            "recent_patterns": [m.get("content", {}).get("summary", "")[:150] for m in memories[:5]],
            "domains": list(set(m.get("domain", "") for m in memories)),
        } if org_memory_col is not None else None,
    }
