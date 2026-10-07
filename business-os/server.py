import os
import uuid
import time
import math
import jwt
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from pymongo import ReturnDocument
from typing import Optional

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from engine import classify_intent, rolling_fields, compute_reengagement_line, llm_turn, llm_complete_action, salaar_route
from db import (
    users_col, threads_col, events_col, telemetry_col, orgs_col, tasks_col, plans_col, members_col,
    async_users_col, async_threads_col, async_events_col, async_telemetry_col, decisions_col,
)
from security import pwd, make_token, revoke_token, cleanup_expired_sessions, set_auth_cookie, clear_auth_cookie, current_user_async, JWT_SECRET
from ledger import record_ledger, inc_stats, ensure_startup
from tracking import router as tracking_router, client_ip, geo_lookup
from admin import router as admin_router
from payments import router as payments_router
from feedback import router as feedback_router
from questionnaire import router as questionnaire_router
from decision_brain import router as brain_router, ensure_brain_startup
from organizations import router as org_router, ensure_org_startup
from founder_profile import router as founder_router
from journey import router as journey_router, ensure_journey_startup
from share import router as share_router, referral_router, ensure_share_startup
from subscriptions import (router as subscriptions_router, deduct_tokens,
                            get_token_budget, ensure_subscriptions_startup)
from executive import router as executive_router, ensure_executive_startup
from execution.router import router as execution_router
from execution.tasks_router import router as tasks_router
from genesis_router import router as genesis_router
import doc_memory
from playbooks import router as playbooks_router
from habits import router as habits_router
from weekly_review import router as weekly_review_router
from system_router import router as system_router
from capabilities_router import router as capabilities_router
from agents import agent_router
from business_os_router import router as business_os_router
from audit_router import router as audit_router
from business_os import ensure_business_os_startup
from audit import ensure_audit_startup
from metrics_router import router as metrics_router
from metrics import ensure_metrics_startup
from loop_router import router as loop_router
from loop import ensure_loop_startup
from automation_router import router as automation_router
from automation_loops import ensure_automation_startup
from governance_router import router as governance_router
from salaar import generate_salaar_brief
from salaar.causal import build_actor_map, simulate_causal_chain, execute_chain_step
from revenue_router import router as revenue_router
from revenue_engine import ensure_revenue_startup
from business_builder_router import router as business_builder_router
from business_builder import ensure_builder_startup
from factory_router import router as factory_router
from factory_bridge import ensure_factory_startup
from growth_engine import ensure_growth_startup

# Turn cost and reserve settings for credit billing
TURN_COST = int(os.environ.get("TURN_COST", "5"))
ULTRA_TURN_COST = int(os.environ.get("ULTRA_TURN_COST", "10"))
SIGNUP_CREDITS = int(os.environ.get("SIGNUP_CREDITS", "100"))
CREDITS_PER_1K_TOKENS = int(os.environ.get("CREDITS_PER_1K_TOKENS", "2"))
TURN_RESERVE_NORMAL = int(os.environ.get("TURN_RESERVE_NORMAL", "8"))
TURN_RESERVE_ULTRA = int(os.environ.get("TURN_RESERVE_ULTRA", "24"))
ASSIST_RESERVE = int(os.environ.get("ASSIST_RESERVE", "10"))
TURN_RESERVE_VISION = int(os.environ.get("TURN_RESERVE_VISION", "40"))


# Compute credit cost from token usage
def token_cost(tokens_in: int, tokens_out: int) -> int:
    total = (tokens_in or 0) + (tokens_out or 0)
    return max(1, math.ceil(total / 1000) * CREDITS_PER_1K_TOKENS)


# Charge tokens and credits after a turn
def deduct_usage(user_id: str, tokens_in: int, tokens_out: int, cost: int):
    try:
        deduct_tokens(user_id, tokens_in, tokens_out)
    except HTTPException:
        pass
    if cost > 0:
        users_col.update_one({"id": user_id, "credits": {"$gte": cost}},
                             {"$inc": {"credits": -cost}})


from ratelimit import general_limiter, strict_limiter

# Enforce a request-rate limit for a key
def _rate_limit(key: str, max_reqs: int = 60, window: float = 60.0):
    limiter = strict_limiter if max_reqs < 60 else general_limiter
    limiter.check(key)

import re as _re

_XSS_PAT = _re.compile(r'(?:<[^>]*\s*(?:on\w+\s*=|javascript\s*:|data\s*:)|<script\b|<iframe\b|<object\b|<embed\b)', _re.I)


# App startup/shutdown: init DB, jobs, and scheduler
@asynccontextmanager
async def _lifespan(app: FastAPI):
    # Always start scheduler even when DB is absent (health checks etc.)
    # Track which startups succeeded so scheduler isn't gated on DB presence
    startup_ok = False
    try:
        ensure_startup()
        ensure_org_startup()
        ensure_brain_startup()
        ensure_journey_startup()
        ensure_share_startup()
        ensure_subscriptions_startup()
        ensure_executive_startup()
        ensure_salaar_startup()
        ensure_business_os_startup()
        ensure_audit_startup()
        ensure_metrics_startup()
        ensure_loop_startup()
        ensure_automation_startup()
        ensure_revenue_startup()
        ensure_builder_startup()
        ensure_factory_startup()
        ensure_growth_startup()
        # Sync connections from Composio on startup for all orgs
        try:
            from execution.connections import refresh_connections_from_composio
            for org in orgs_col.find({}, {"_id": 0, "id": 1}):
                try:
                    refresh_connections_from_composio(org["id"])
                except Exception:
                    pass
            log.info("connection sync complete")
        except Exception:
            pass
        startup_ok = True
    except Exception as e:
        log.warning(f"Startup init failed (DB may not be ready): {e}")
    if not scheduler.running:
        try:
            scheduler.start()
            log.info(f"scheduler started (startup_ok={startup_ok})")
        except Exception as e:
            log.warning(f"scheduler start failed: {e}")
    try:
        from playbooks import PLAYBOOKS as _P
        log.info(f"playbooks loaded: {len(_P)} frameworks")
    except Exception:
        pass
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


# Create the FastAPI application instance
app = FastAPI(title="SmartDecigen Deep Discussion Engine",
              docs_url=None if os.environ.get("DISABLE_DOCS") else "/docs",
              redoc_url=None if os.environ.get("DISABLE_DOCS") else "/redoc",
              lifespan=_lifespan)

# WWW redirect, XSS scan, and security headers
@app.middleware("http")
async def _security_middleware(request: Request, call_next):
    host = request.headers.get("host", "").lower().split(":")[0]
    if host == "smartdecigen.com":
        from fastapi.responses import RedirectResponse
        path = request.url.path
        qs = ("?" + request.url.query) if request.url.query else ""
        return RedirectResponse(f"https://www.smartdecigen.com{path}{qs}", status_code=301)
    # XSS scan: read body without draining it for downstream handlers
    # FastAPI caches body after first read, but we must not break streaming
    ctype = request.headers.get("content-type", "")
    # Only scan json/form bodies, skip multipart/file uploads
    if ctype and ("json" in ctype or "x-www-form-urlencoded" in ctype):
        try:
            body = await request.body()
            if body:
                text = body.decode("utf-8", errors="replace")
                if _XSS_PAT.search(text):
                    return JSONResponse({"detail": "Request blocked: suspicious content detected"}, status_code=400)
                # Restore body so Pydantic can read it
                async def _receive():
                    return {"type": "http.request", "body": body}
                request._receive = _receive
        except Exception:
            pass
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline' https://*.firebaseapp.com https://assets.emergent.sh; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; img-src 'self' data:; font-src 'self' data: https://fonts.gstatic.com; connect-src 'self' https:; frame-src 'none'; object-src 'none'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response

api = APIRouter(prefix="/api")
v1 = APIRouter(prefix="/api/v1")  # Ch.54: versioned API — all new endpoints go here
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sdg")

# Current UTC timestamp helper
def now_utc():
    return datetime.now(timezone.utc)

# Strip _id and ISO-format datetimes for JSON
def serialize(doc):
    if isinstance(doc, dict):
        return {k: serialize(v) for k, v in doc.items() if k != "_id"}
    if isinstance(doc, list):
        return [serialize(x) for x in doc]
    if isinstance(doc, datetime):
        return doc.isoformat()
    return doc

# Coerce naive datetimes to UTC-aware
def as_aware(dt):
    if dt and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

# Signup request payload
class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = ""
    ref: str = ""

# Login request payload
class LoginIn(BaseModel):
    email: EmailStr
    password: str

# Goal-thread creation payload
class GoalIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    why_now: str = Field(min_length=3, max_length=2000)

# Discussion turn payload with optional attachment
class TurnIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    mode: str = "normal"
    adjust: bool = False
    attachment_base64: Optional[str] = None
    attachment_filename: Optional[str] = None
    attachment_mime: Optional[str] = None

# Thread status change payload
class StatusIn(BaseModel):
    status: str


# Public pricing/config settings
@api.get("/config")
async def public_config():
    return {"signup_credits": int(os.environ.get("SIGNUP_CREDITS", 100))}


# Create an account, org, and agents
@api.post("/auth/signup")
async def signup(body: SignupIn, request: Request):
    _rate_limit(f"signup:{client_ip(request)}", max_reqs=5, window=300.0)
    existing = await async_users_col.find_one({"email": body.email.lower()})
    if existing:
        raise HTTPException(409, "An account with this email already exists")
    ip = client_ip(request)
    geo = geo_lookup(ip)
    name = body.name.strip()
    if _XSS_PAT.search(name):
        raise HTTPException(400, "Name cannot contain script tags or event handlers")
    user = {
        "id": str(uuid.uuid4()),
        "email": body.email.lower(),
        "name": body.name.strip(),
        "password_hash": pwd.hash(body.password),
        "credits": SIGNUP_CREDITS,
        "created_at": now_utc(),
        "country": geo["country"], "city": geo["city"], "last_ip": ip,
        "questions_asked": 0, "tokens_in": 0, "tokens_out": 0,
        "credits_issued_free": SIGNUP_CREDITS, "credits_issued_paid": 0,
    }
    await async_users_col.insert_one(user)
    record_ledger(user["id"], "free_grant", SIGNUP_CREDITS, reason="signup")
    inc_stats({"credits_issued_free": SIGNUP_CREDITS})

    # Auto-create organization + init agents for instant company setup
    try:
        org_id = str(uuid.uuid4())
        org_name = (body.name.strip() + "'s Company") if body.name.strip() else "My Company"
        org = {
            "id": org_id, "name": org_name, "owner_user_id": user["id"],
            "member_count": 1, "created_at": now_utc(),
        }
        orgs_col.insert_one(org)
        members_col.insert_one({
            "user_id": user["id"], "org_id": org_id, "role": "owner",
            "status": "active", "joined_at": now_utc(),
        })
        users_col.update_one({"id": user["id"]}, {
            "$set": {"org_id": org_id, "org_role": "owner"}})
        user["org_id"] = org_id
        user["org_role"] = "owner"
        log.info(f"auto-created org '{org_name}' for user {user['email']}")

        # Initialize 12 agents (background, non-blocking)
        try:
            from agents import AGENT_DEFINITIONS, create_agent
            for atype in AGENT_DEFINITIONS:
                create_agent(org_id, atype, user["id"])
            log.info(f"auto-init 12 agents for org {org_id}")
        except Exception as e:
            log.warning(f"agent init failed (non-fatal): {e}")
    except Exception as e:
        log.warning(f"auto-org creation failed (non-fatal): {e}")
        # Don't block signup if org creation fails — user can create one later
    ref = (body.ref or "").strip()
    if ref:
        referrer = users_col.find_one({"referral_code": ref}, {"id": 1, "email": 1})
        if referrer and referrer["id"] != user["id"]:
            bonus = int(os.environ.get("REFERRAL_BONUS", "25"))
            users_col.update_one({"id": user["id"]}, {
                "$set": {"referred_by": referrer["id"]},
                "$inc": {"credits": bonus, "credits_issued_free": bonus}})
            users_col.update_one({"id": referrer["id"]}, {"$inc": {"credits": bonus, "credits_issued_free": bonus}})
            record_ledger(user["id"], "referral_bonus", bonus, reason="signed up with a referral")
            record_ledger(referrer["id"], "referral_bonus", bonus, reason=f"invited {user['email']}")
            inc_stats({"credits_issued_free": 2 * bonus})
            user["credits"] += bonus
    _, jwt_str = make_token(user["id"])
    resp = JSONResponse({"user": {"id": user["id"], "email": user["email"], "name": user["name"], "credits": user["credits"], "is_admin": False, "questionnaire_completed": False, "org_id": user.get("org_id"), "org_role": user.get("org_role")}})
    set_auth_cookie(resp, jwt_str)
    return resp

# Authenticate and issue a session cookie
@api.post("/auth/login")
async def login(body: LoginIn, request: Request):
    _rate_limit(f"login:{client_ip(request)}", max_reqs=10, window=300.0)
    user = await async_users_col.find_one({"email": body.email.lower()})
    if not user or not pwd.verify(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    ip = client_ip(request)
    await async_users_col.update_one({"id": user["id"]}, {"$set": {"last_login_at": now_utc(), "last_ip": ip}})
    if not user.get("country"):
        geo = geo_lookup(ip)
        await async_users_col.update_one({"id": user["id"]}, {"$set": {"country": geo["country"], "city": geo["city"]}})
    _, jwt_str = make_token(user["id"])
    resp = JSONResponse({"user": {"id": user["id"], "email": user["email"], "name": user.get("name", ""), "credits": user.get("credits", 0), "is_admin": bool(user.get("is_admin")), "questionnaire_completed": bool(user.get("questionnaire_completed")), "org_id": user.get("org_id"), "org_role": user.get("org_role")}})
    set_auth_cookie(resp, jwt_str)
    return resp

# Return the authenticated user's profile
@api.get("/auth/me")
async def me(user: dict = Depends(current_user_async)):
    return {"id": user["id"], "phone": user.get("phone", ""), "email": user.get("email", ""), "name": user.get("name", ""), "credits": user.get("credits", 0), "is_admin": bool(user.get("is_admin")), "questionnaire_completed": bool(user.get("questionnaire_completed")), "org_id": user.get("org_id"), "org_role": user.get("org_role")}


# Revoke the session token and clear cookie
@api.post("/auth/logout")
async def logout(request: Request, user: dict = Depends(current_user_async)):
    token = request.cookies.get("sdg_token")
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            revoke_token(payload.get("jti", ""))
        except Exception:
            pass
    resp = JSONResponse({"ok": True})
    clear_auth_cookie(resp)
    return resp


# Run one engine turn and persist thread state
def run_pipeline(thread: dict, user: dict, message: str, mode: str = "normal",
                 intent_override: str = None, attachment: Optional[dict] = None,
                 attachment_preview: Optional[dict] = None):
    t0 = time.time()
    now = now_utc()
    last_at = as_aware(thread.get("last_turn_at")) or as_aware(thread["opened_at"])
    days_gap = (now - last_at).total_seconds() / 86400
    events = list(events_col.find({"thread_id": thread["thread_id"]}))
    for e in events:
        e["at"] = as_aware(e["at"])
    substrate = rolling_fields(events, now)
    streak = 0
    for e in sorted(events, key=lambda x: x["at"], reverse=True):
        if e.get("action_done"):
            streak += 1
        else:
            break
    substrate["streak"] = streak
    intent = intent_override or classify_intent(message, days_gap)
    route = salaar_route(message, thread, user)
    if route != "engine":
        log.info(f"salaar route: {route} for user {user.get('id','')[:8]} intent={intent}")
    user_doc = users_col.find_one({"id": user["id"]}) or user
    understanding = (user_doc or {}).get("understanding")
    user_doc = users_col.find_one({"id": user["id"]}) or user
    try:
        recall_block = doc_memory.recall(thread["thread_id"], message)
    except Exception as e:
        log.warning(f"doc recall failed: {e}")
        recall_block = ""
    out, model, usage = llm_turn(thread, substrate, message, intent, mode,
                                 attachment=attachment, user_doc=user_doc,
                                 recall_block=recall_block,
                                 attachment_preview=attachment_preview,
                                 understanding=understanding,
                                 org_id=user_doc.get("org_id"))
    sig = out["signals"]
    events_col.insert_one({
        "id": str(uuid.uuid4()), "thread_id": thread["thread_id"], "user_id": user["id"], "at": now,
        "emotional_temperature": float(sig.get("emotional_temperature", 0.5)),
        "action_assigned": True, "action_done": bool(sig.get("action_done")),
        "contradiction": sig.get("contradiction"),
    })
    events.append({"at": now, "emotional_temperature": float(sig.get("emotional_temperature", 0.5)),
                   "action_assigned": True, "action_done": bool(sig.get("action_done")),
                   "contradiction": sig.get("contradiction")})
    new_snapshot = rolling_fields(events, now)
    new_snapshot["summary_line"] = out["state_summary"].split("\n")[0][:160]
    new_msgs = [
        {"role": "user", "text": message, "at": now, "intent": intent},
        {"role": "engine", "text": out["acknowledgment"], "mirror": out.get("mirror"), "at": now},
    ]
    threads_col.update_one({"thread_id": thread["thread_id"]}, {
        "$set": {
            "current_state_summary": out["state_summary"],
            "current_open_question": out["refreshed_open_question"],
            "current_easiest_path": out.get("refreshed_easiest_path") or thread.get("current_easiest_path") or "(still exploring)",
            "current_next_action": out.get("refreshed_next_action") or None,
            "current_phase": out.get("phase") or "exploring",
            "current_action_payoff": (out.get("action_payoff") or "").strip() or None,
            "current_big_picture": (out.get("big_picture_link") or "").strip() or None,
            "current_bold_move": (out.get("bold_move") or "").strip() or None,
            "current_outbox": (out.get("outbox_alternative") or "").strip() or None,
            "current_requested_input": (out.get("requested_input") or "").strip() or None,
            "current_mirror": out.get("mirror"),
            "current_insight": (out.get("insight") or "").strip() or None,
            "current_action_artifact": None,
            "current_mode": out.get("mode") or "advice",
            "current_key_takeaway": (out.get("key_takeaway") or "").strip() or None,
            "current_recommendation": out.get("recommendation"),
            "current_plan": out.get("plan"),
            "current_citations": out.get("citations") or [],
            "current_found_in_docs": bool(out.get("found_in_docs")),
            "current_predicted_outcome": out.get("predicted_outcome"),
            "current_dont_follow_if": out.get("dont_follow_if"),
            "skip_list": out.get("skip_list", []),
            "last_turn_at": now,
            "snapshot_at_last_turn": new_snapshot,
            "rolling": {k: new_snapshot[k] for k in ("emotional_temperature", "execution_consistency", "pace_calibration")},
            **({"current_file_facts": (out.get("file_facts") or "").strip()} if (out.get("file_facts") or "").strip() else {}),
        },
        "$push": {"messages": {"$each": new_msgs}},
    })
    # ── Merged engine: persist the decision record (brain ledger) for every turn ──
    try:
        _mode = out.get("mode") or "advice"
        _reasoning = out.get("reasoning") if isinstance(out.get("reasoning"), dict) else {}
        _po = out.get("predicted_outcome")
        _cost = token_cost(usage["input_tokens"], usage["output_tokens"])
        _decision = {
            "id": str(uuid.uuid4()),
            "org_id": user.get("org_id"),
            "user_id": user["id"],
            "user_name": user.get("name", "") or "",
            "session_id": f"thread_{thread['thread_id']}",
            "question": message[:4000],
            "mode": _mode,
            "found_in_docs": out.get("found_in_docs"),
            "situation_read": out.get("mirror") or "",
            "answer": out["acknowledgment"],
            "recommendation": out.get("recommendation"),
            "plan": out.get("plan"),
            "next_action": (out.get("refreshed_next_action") or "").strip() or None,
            "hook": out.get("key_takeaway") or "",
            "sharpening_question": out.get("refreshed_open_question") if (out.get("refreshed_open_question") or "").strip() and (out.get("refreshed_open_question") or "") != "(none yet)" else None,
            "citations": out.get("citations") or [],
            "model": model,
            "cost": _cost,
            "tokens": usage["input_tokens"] + usage["output_tokens"],
            "created_at": now,
            "committed_action": None,
            "due_at": None,
            "result": None,
            "status": "open",
            "strategic_alignment": None,
            "reasoning": _reasoning,
            "function": "general",
            "revenue_proximity": "core",
            "strategy_version": 0,
            "alignment_band": None,
            "outcome": {"status": "unknown", "score": None, "source": None, "at": None},
            "predicted_outcome": _po,
            "dont_follow_if": out.get("dont_follow_if"),
            "review_at": ((now + timedelta(days=_po["review_after_days"])) if _po else None),
            "reviewed_at": None,
            "impact_inr": None,
            "source": "thread",
        }
        decisions_col.insert_one(_decision)
    except Exception as _de:
        log.warning(f"decision record persist failed (non-fatal): {_de}")
    latency = round(time.time() - t0, 2)
    actual_cost = token_cost(usage["input_tokens"], usage["output_tokens"])
    telemetry_col.insert_one({"id": str(uuid.uuid4()), "type": "discussion_turn", "user_id": user["id"],
                              "thread_id": thread["thread_id"], "intent": intent, "model": model,
                              "mode": mode, "cost": actual_cost,
                              "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"],
                              "latency_s": latency, "response_len": len(out["acknowledgment"]), "at": now})
    user_set = {"last_active_at": now}
    _understanding = out.get("understanding")
    if isinstance(_understanding, dict) and any((str(v).strip() for v in _understanding.values())):
        user_set["understanding"] = _understanding
    users_col.update_one({"id": user["id"]}, {
        "$inc": {"questions_asked": 1, "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"]},
        "$set": user_set})
    # ---- Ch.X: Store MCP execution evidence in thread ----
    execution = out.get("_execution")
    if execution:
        threads_col.update_one({"thread_id": thread["thread_id"]}, {
            "$push": {"execution_log": {"$each": [{"at": now, "actions": execution}]}}})
    inc_stats({"questions_total": 1, ("turns_ultra" if mode == "ultra" else "turns_normal"): 1,
               "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"]})

    # Audit trail: record every turn
    try:
        org_id = user.get("org_id")
        if org_id:
            from audit import record_turn
            record_turn(org_id, user["id"], thread["thread_id"], intent, model,
                        usage["input_tokens"] + usage["output_tokens"])
    except Exception:
        pass
    # ── SALAAR: outcome learning loop — when founder reports progress, store pattern→outcome ──
    if intent == "acknowledgment" and user.get("org_id"):
        try:
            from salaar.inline import salaar_outcome_learn
            salaar_outcome_learn(
                user["org_id"], "execution_stalling", "resolved",
                {"thread_id": thread["thread_id"], "goal": thread["goal"], "action": message[:200]}
            )
        except Exception:
            pass
    return out, intent, model, latency, usage


# Open a new goal thread with first turn
@api.post("/goals")
async def create_goal(body: GoalIn, request: Request, user: dict = Depends(current_user_async)):
    _rate_limit(f"goal:{user['id']}", max_reqs=5, window=300.0)
    reserve = TURN_RESERVE_NORMAL
    u = users_col.find_one_and_update({"id": user["id"], "credits": {"$gte": reserve}},
                                      {"$inc": {"credits": -reserve}}, return_document=ReturnDocument.AFTER)
    if not u:
        raise HTTPException(402, "Not enough credits")
    now = now_utc()
    try:
        geo = geo_lookup(client_ip(request)) or {}
        user_geo = {"city": geo.get("city") or "", "country": geo.get("country") or "",
                    "country_code": geo.get("country_code") or ""}
    except Exception as e:
        log.warning(f"geo lookup failed: {e}")
        user_geo = {}
    thread = {
        "thread_id": str(uuid.uuid4()), "user_id": user["id"],
        "goal": body.title.strip(), "why_now": body.why_now.strip(),
        "opened_at": now, "status": "active",
        "current_state_summary": "(opening)", "current_open_question": "(none yet)",
        "current_easiest_path": "(none yet)", "current_next_action": "(none yet)",
        "current_phase": "exploring",
        "current_action_payoff": None, "current_big_picture": None, "current_bold_move": None,
        "current_outbox": None,
        "user_geo": user_geo,
        "skip_list": [], "messages": [], "last_turn_at": None, "snapshot_at_last_turn": None,
        "rolling": {"emotional_temperature": 0.5, "execution_consistency": 0.5, "pace_calibration": "on-track"},
    }
    # Ch.33: stamp with current mission version for traceability
    org = orgs_col.find_one({"id": user.get("org_id")}) if user.get("org_id") else None
    if org:
        thread["mission_version"] = org.get("strategy_version", 0)
    threads_col.insert_one(thread)
    try:
        out, intent, model, latency, usage = run_pipeline(thread, user, body.why_now.strip())
    except Exception as e:
        try:
            users_col.update_one({"id": user["id"]}, {"$inc": {"credits": reserve}})
        except Exception as refund_err:
            log.error(f"CRITICAL: refund failed after goal-open LLM failure for user={user['id']} reserve={reserve}: {refund_err}")
        threads_col.delete_one({"thread_id": thread["thread_id"]})
        log.error(f"goal creation turn failed: {e}")
        raise HTTPException(502, "The engine could not open this thread. You were not charged — try again.")
    actual = token_cost(usage["input_tokens"], usage["output_tokens"])
    deduct_usage(user["id"], usage["input_tokens"], usage["output_tokens"], actual)
    refund = max(0, reserve - actual)
    if refund:
        u = users_col.find_one_and_update({"id": user["id"]}, {"$inc": {"credits": refund}},
                                          return_document=ReturnDocument.AFTER)
    record_ledger(user["id"], "turn_spend", -actual, thread_id=thread["thread_id"], mode="normal",
                  tokens=usage["input_tokens"] + usage["output_tokens"], reason="goal_opening")
    inc_stats({"credits_spent": actual})
    fresh = threads_col.find_one({"thread_id": thread["thread_id"]})
    token_budget = get_token_budget(user["id"])
    return {"thread": serialize(fresh), "acknowledgment": out["acknowledgment"], "credits": u["credits"],
            "cost": actual, "tokens": usage["input_tokens"] + usage["output_tokens"],
            "token_usage": token_budget}

# List threads plus momentum stats
@api.get("/goals")
async def list_goals(user: dict = Depends(current_user_async)):
    now = now_utc()
    items = []
    cursor = async_threads_col.find({"user_id": user["id"]}).sort("opened_at", -1)
    async for t in cursor:
        last_at = as_aware(t.get("last_turn_at"))
        hours_since = (now - last_at).total_seconds() / 3600 if last_at else None
        items.append({
            "thread_id": t["thread_id"], "goal": t["goal"], "status": t["status"],
            "pace": t.get("rolling", {}).get("pace_calibration", "on-track"),
            "consistency": t.get("rolling", {}).get("execution_consistency", 0.5),
            "next_action": t.get("current_next_action", ""),
            "open_question": t.get("current_open_question", ""),
            "action_overdue": bool(t["status"] == "active" and hours_since is not None and hours_since > 48),
            "hours_since_turn": round(hours_since) if hours_since is not None else None,
            "opened_at": t["opened_at"].isoformat() if isinstance(t.get("opened_at"), datetime) else t.get("opened_at"),
            "last_turn_at": t["last_turn_at"].isoformat() if isinstance(t.get("last_turn_at"), datetime) else t.get("last_turn_at"),
        })
    kept = await async_events_col.count_documents({"user_id": user["id"], "action_done": True})
    week_ago = now - timedelta(days=7)
    turns_week = await async_telemetry_col.count_documents({"user_id": user["id"], "type": "discussion_turn", "at": {"$gte": week_ago}})
    active = [g for g in items if g["status"] == "active"]
    avg_consistency = round(sum(g["consistency"] for g in active) / len(active), 2) if active else None
    return {"goals": items, "momentum": {"kept_promises": kept, "turns_this_week": turns_week,
                                         "avg_consistency": avg_consistency}}

# Fetch a thread with re-engagement line
@api.get("/threads/{thread_id}")
async def get_thread(thread_id: str, user: dict = Depends(current_user_async)):
    t = await async_threads_col.find_one({"thread_id": thread_id, "user_id": user["id"]})
    if not t:
        raise HTTPException(404, "Thread not found")
    now = now_utc()
    reengagement = None
    silence_days = None
    last_at = as_aware(t.get("last_turn_at"))
    if last_at and t["status"] == "active":
        days = int((now - last_at).total_seconds() // 86400)
        if days >= 7 and t.get("snapshot_at_last_turn"):
            events = list(events_col.find({"thread_id": thread_id}))
            for e in events:
                e["at"] = as_aware(e["at"])
            now_snap = rolling_fields(events, now)
            reengagement = compute_reengagement_line(t["snapshot_at_last_turn"], now_snap, days)
            if reengagement:
                telemetry_col.insert_one({"id": str(uuid.uuid4()), "type": "reengagement_shown",
                                          "user_id": user["id"], "thread_id": thread_id, "at": now})
        if days >= 14:
            silence_days = days
    hours_since = (now - last_at).total_seconds() / 3600 if last_at else None
    action_overdue = bool(t["status"] == "active" and hours_since is not None and hours_since > 48)
    return {"thread": serialize(t), "reengagement_line": reengagement, "silence_days": silence_days,
            "action_overdue": action_overdue,
            "hours_since_turn": round(hours_since) if hours_since is not None else None}

# Run a discussion turn with credit accounting
@api.post("/threads/{thread_id}/turn")
async def turn(thread_id: str, body: TurnIn, request: Request, background: BackgroundTasks, user: dict = Depends(current_user_async)):
    _rate_limit(f"turn:{user['id']}", max_reqs=15, window=60.0)
    if body.mode not in ("normal", "ultra"):
        raise HTTPException(422, "mode must be 'normal' or 'ultra'")
    if body.mode == "ultra":
        budget = get_token_budget(user["id"])
        if not budget.get("ultra_enabled"):
            raise HTTPException(402, "Ultra thinking requires a Pro subscription. Upgrade to use this feature.")
    try:
        fresh = geo_lookup(client_ip(request)) or {}
        if fresh.get("city") and fresh.get("city") not in ("Unknown", "Local"):
            async_threads_col.update_one({"thread_id": thread_id, "user_id": user["id"],
                                          "user_geo.city": {"$ne": fresh.get("city")}},
                                         {"$set": {"user_geo": {"city": fresh.get("city"),
                                                                "country": fresh.get("country"),
                                                                "country_code": fresh.get("country_code", "")}}})
    except Exception as e:
        log.debug(f"per-turn geo refresh skipped: {e}")
    attachment = None
    attachment_preview = None
    if body.attachment_base64:
        if len(body.attachment_base64) > 12_000_000:
            raise HTTPException(413, "Attachment too large. Keep files under 8 MB.")
        attachment = {"base64": body.attachment_base64,
                      "filename": body.attachment_filename or "attachment",
                      "mime": body.attachment_mime or ""}
        try:
            vblocks, inline_text, tree_id = doc_memory.extract(
                attachment["filename"], attachment["mime"], attachment["base64"], thread_id)
            attachment_preview = {"vision_blocks": vblocks, "inline_text": inline_text}
            if tree_id:
                import base64 as _b64
                raw = _b64.b64decode(attachment["base64"])
                kind, full_text, chapters = doc_memory.parse_file(
                    attachment["filename"], attachment["mime"], raw)
                background.add_task(doc_memory.build_tree_sync, tree_id, full_text, chapters, attachment["filename"])
        except Exception as e:
            log.warning(f"doc pre-extract failed, falling back to engine inline: {e}")
            attachment_preview = None
    if attachment:
        reserve = TURN_RESERVE_VISION
    elif body.mode == "ultra":
        reserve = TURN_RESERVE_ULTRA
    else:
        reserve = TURN_RESERVE_NORMAL
    t = await async_threads_col.find_one({"thread_id": thread_id, "user_id": user["id"]})
    if not t:
        raise HTTPException(404, "Thread not found")
    if t["status"] != "active":
        raise HTTPException(400, f"This thread is {t['status']}. Reactivate it to continue.")
    u = users_col.find_one_and_update({"id": user["id"], "credits": {"$gte": reserve}},
                                      {"$inc": {"credits": -reserve}}, return_document=ReturnDocument.AFTER)
    if not u:
        raise HTTPException(402, "Not enough credits")
    try:
        out, intent, model, latency, usage = run_pipeline(t, user, body.message.strip(), body.mode,
                                                   intent_override="action_adjust" if body.adjust else None,
                                                   attachment=attachment,
                                                   attachment_preview=attachment_preview)
    except Exception as e:
        try:
            users_col.update_one({"id": user["id"]}, {"$inc": {"credits": reserve}})
        except Exception as refund_err:
            log.error(f"CRITICAL: refund failed after turn LLM failure for user={user['id']} reserve={reserve}: {refund_err}")
        log.error(f"turn failed: {e}")
        raise HTTPException(502, "The engine did not respond. You were not charged — try again.")
    actual = token_cost(usage["input_tokens"], usage["output_tokens"])
    deduct_usage(user["id"], usage["input_tokens"], usage["output_tokens"], actual)
    refund = max(0, reserve - actual)
    if refund:
        u = users_col.find_one_and_update({"id": user["id"]}, {"$inc": {"credits": refund}},
                                          return_document=ReturnDocument.AFTER)
    record_ledger(user["id"], "turn_spend", -actual, thread_id=thread_id, mode=body.mode,
                  tokens=usage["input_tokens"] + usage["output_tokens"],
                  reason="vision_turn" if attachment else None)
    inc_stats({"credits_spent": actual})
    fresh = threads_col.find_one({"thread_id": thread_id})
    token_budget = get_token_budget(user["id"])
    return {"thread": serialize(fresh), "acknowledgment": out["acknowledgment"],
            "intent": intent, "credits": u["credits"], "model": model, "mode": body.mode,
            "cost": actual, "tokens": usage["input_tokens"] + usage["output_tokens"],
            "had_attachment": bool(attachment),
            "token_usage": token_budget}

# Generate the do-it-for-me artifact
@api.post("/threads/{thread_id}/complete-action")
async def complete_action(thread_id: str, user: dict = Depends(current_user_async)):
    t = await async_threads_col.find_one({"thread_id": thread_id, "user_id": user["id"]})
    if not t:
        raise HTTPException(404, "Thread not found")
    if t["status"] != "active":
        raise HTTPException(400, f"This thread is {t['status']}. Reactivate it to continue.")
    if not t.get("current_next_action") or t["current_next_action"].startswith("(none"):
        raise HTTPException(400, "No next action to complete yet.")
    reserve = ASSIST_RESERVE
    u = users_col.find_one_and_update({"id": user["id"], "credits": {"$gte": reserve}},
                                      {"$inc": {"credits": -reserve}}, return_document=ReturnDocument.AFTER)
    if not u:
        raise HTTPException(402, "Not enough credits")
    t0 = time.time()
    try:
        fresh_user = users_col.find_one({"id": user["id"]}) or user
        out, model, usage = llm_complete_action(t, user_doc=fresh_user)
    except Exception as e:
        users_col.update_one({"id": user["id"]}, {"$inc": {"credits": reserve}})
        log.error(f"complete-action failed: {e}")
        raise HTTPException(502, "The engine could not prepare this. You were not charged — try again.")
    total_tokens = usage["input_tokens"] + usage["output_tokens"]
    cost = token_cost(usage["input_tokens"], usage["output_tokens"])
    deduct_usage(user["id"], usage["input_tokens"], usage["output_tokens"], cost)
    refund = max(0, reserve - cost)
    if refund:
        u = users_col.find_one_and_update({"id": user["id"]}, {"$inc": {"credits": refund}},
                                          return_document=ReturnDocument.AFTER)
    now = now_utc()
    users_col.update_one({"id": user["id"]}, {
        "$inc": {"tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"]},
        "$set": {"last_active_at": now}})
    artifact = {
        "kind": out.get("kind", "draft"), "title": out.get("title", "Your draft"),
        "channel": out.get("channel", "other"), "subject": out.get("subject"),
        "artifact": out["artifact"], "steps": out.get("steps", []),
        "handoff": out["handoff"], "time_estimate_min": out.get("time_estimate_min"),
        "generated_at": now, "model": model, "cost": cost, "tokens": total_tokens,
    }
    threads_col.update_one({"thread_id": thread_id}, {"$set": {"current_action_artifact": artifact}})
    record_ledger(user["id"], "action_assist", -cost, thread_id=thread_id,
                  tokens=total_tokens, reason="do_it_for_me")
    inc_stats({"credits_spent": cost, "assists_total": 1,
               "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"]})
    telemetry_col.insert_one({"id": str(uuid.uuid4()), "type": "action_assist", "user_id": user["id"],
                              "thread_id": thread_id, "model": model, "cost": cost,
                              "tokens_in": usage["input_tokens"], "tokens_out": usage["output_tokens"],
                              "latency_s": round(time.time() - t0, 2), "at": now})
    token_budget = get_token_budget(user["id"])
    return {"artifact": serialize(artifact), "credits": u.get("credits", 0), "cost": cost,
            "tokens": total_tokens, "token_usage": token_budget}

# Change a thread's lifecycle status
@api.patch("/threads/{thread_id}/status")
async def set_status(thread_id: str, body: StatusIn, user: dict = Depends(current_user_async)):
    if body.status not in ("active", "paused", "graduated", "released"):
        raise HTTPException(422, "Invalid status")
    r = await async_threads_col.update_one({"thread_id": thread_id, "user_id": user["id"]}, {"$set": {"status": body.status}})
    if r.matched_count == 0:
        raise HTTPException(404, "Thread not found")
    return {"ok": True, "status": body.status}

# Return credit balance and pricing
@api.get("/credits")
async def credits(user: dict = Depends(current_user_async)):
    return {"credits": user.get("credits", 0),
            "turn_cost": TURN_COST, "ultra_turn_cost": ULTRA_TURN_COST,
            "credits_per_1k_tokens": CREDITS_PER_1K_TOKENS,
            "turn_reserve_normal": TURN_RESERVE_NORMAL,
            "turn_reserve_ultra": TURN_RESERVE_ULTRA,
            "assist_reserve": ASSIST_RESERVE}

# Service metadata for the API root
@api.get("/")
def root():
    return {"service": "SmartDecigen Deep Discussion Engine", "status": "ok", "version": "1"}


@api.get("/health")
def health():
    """Lightweight health check — no DB, no filesystem. Used by Railway."""
    return {"status": "ok"}

# Service metadata for the versioned root
@v1.get("")
def v1_root():
    return {"service": "SmartDecigen Deep Discussion Engine", "status": "ok", "version": "1"}  # ponytail: duplicate needed for /api/v1 root

# Serve a deny-all robots.txt
@api.get("/robots.txt", include_in_schema=False)
def robots():
    from fastapi.responses import Response
    return Response(content="User-agent: *\nDisallow: /\n", media_type="text/plain")

# Generate the SALAAR company brief
@api.get("/salaar/brief")
async def salaar_brief_endpoint(user: dict = Depends(current_user_async)):
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(400, "No organization — SALAAR requires a company workspace")
    return generate_salaar_brief(org_id, user["id"])

# ── SALAAR Causal Engine API ──
class CausalIn(BaseModel):
    objective: str = Field(min_length=3, max_length=2000)
    context: str = ""

@api.post("/salaar/chain/simulate")
async def salaar_simulate_chain(body: CausalIn, user: dict = Depends(current_user_async)):
    """Simulate a complete causal chain for achieving an objective."""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(400, "No organization — SALAAR requires a company workspace")
    # Build actor map
    actor_map = build_actor_map(org_id, body.objective, body.context)
    if actor_map.get("error"):
        raise HTTPException(502, f"Actor mapping failed: {actor_map['error']}")
    # Simulate chain
    chain = simulate_causal_chain(org_id, body.objective, actor_map, body.context)
    if chain.get("error"):
        raise HTTPException(502, f"Chain simulation failed: {chain['error']}")
    return {"chain": chain, "actor_map": actor_map}

@api.post("/salaar/chain/{chain_id}/execute-step/{step_number}")
async def salaar_execute_step(chain_id: str, step_number: int, user: dict = Depends(current_user_async)):
    """Execute one step in a causal chain."""
    org_id = user.get("org_id")
    if not org_id:
        raise HTTPException(400, "No organization")
    from salaar.causal import CAUSAL_CHAINS_COL
    chain = CAUSAL_CHAINS_COL.find_one({"id": chain_id, "org_id": org_id}) if CAUSAL_CHAINS_COL is not None else None
    if not chain:
        raise HTTPException(404, "Chain not found")
    steps = chain.get("steps", [])
    step = next((s for s in steps if s.get("step") == step_number), None)
    if not step:
        raise HTTPException(404, "Step not found")
    actor_map = {"actors": chain.get("actors", [])}
    result = execute_chain_step(org_id, step, actor_map, chain.get("objective", ""))
    return {"step": step_number, "result": result}

app.include_router(api)
app.include_router(v1)  # Ch.54: versioned API — new endpoints go under /api/v1

FRONTEND_BUILD = Path(__file__).parent.parent / "frontend" / "build"
if FRONTEND_BUILD.is_dir():
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse

    # Vite outputs build/assets; older CRA builds used build/static. Mount what exists.
    for _sub in ("assets", "static"):
        _dir = FRONTEND_BUILD / _sub
        if _dir.is_dir():
            app.mount(f"/{_sub}", StaticFiles(directory=str(_dir)), name=f"frontend-{_sub}")

    # Serve SPA index or JSON for missing routes
    @app.exception_handler(404)
    async def _spa_fallback(request: Request, exc):
        # API 404s must stay JSON 404s — swallowing them returns 200+HTML to API
        # clients and masks real errors. Only client-side routes get index.html.
        if request.url.path.startswith("/api"):
            from fastapi.responses import JSONResponse
            detail = getattr(exc, "detail", None) or "Not Found"
            return JSONResponse({"detail": detail}, status_code=404)
        # Real build files (favicon, manifest, …) are served as themselves.
        candidate = (FRONTEND_BUILD / request.url.path.lstrip("/")).resolve()
        if candidate.is_file() and str(candidate).startswith(str(FRONTEND_BUILD.resolve())):
            return FileResponse(str(candidate))
        return FileResponse(str(FRONTEND_BUILD / "index.html"), media_type="text/html",
                            headers={"Cache-Control": "no-cache, no-store, must-revalidate"})

    log.info(f"frontend build served from {FRONTEND_BUILD}")

app.include_router(tracking_router)
app.include_router(admin_router)
app.include_router(payments_router)
app.include_router(feedback_router)
app.include_router(questionnaire_router)
app.include_router(brain_router)
app.include_router(org_router)
app.include_router(founder_router)
app.include_router(journey_router)
app.include_router(share_router)
app.include_router(referral_router)
app.include_router(subscriptions_router)
app.include_router(executive_router)
app.include_router(execution_router)
app.include_router(tasks_router)
app.include_router(genesis_router)
app.include_router(playbooks_router)
app.include_router(habits_router)
app.include_router(weekly_review_router)
app.include_router(system_router)
app.include_router(capabilities_router)
app.include_router(agent_router)
app.include_router(business_os_router)
app.include_router(audit_router)
app.include_router(metrics_router)
app.include_router(loop_router)
app.include_router(automation_router)
app.include_router(governance_router)
app.include_router(revenue_router)
app.include_router(business_builder_router)
app.include_router(factory_router)

scheduler = BackgroundScheduler(daemon=True)


def _kr_desc(kr):
    """Extract description from a KR, whether string or dict."""
    if isinstance(kr, dict):
        return kr.get("description", str(kr))[:120]
    return str(kr)[:120]


# Weekly job: generate tasks from active plans
def _saturday_night_generate():
    log.info("scheduler: Saturday night task generation starting")
    try:
        plans = list(plans_col.find({"status": "active"}))
        for plan in plans:
            try:
                org_id = plan["org_id"]
                from organizations import _get_next_monday, _best_member_for_function, TASK_GENERATION_SYSTEM, norm_dep_function
                from engine import client, _extract_json, PRIMARY_MODEL
                import json, uuid
                from datetime import timedelta

                org = orgs_col.find_one({"id": org_id})
                north_star = (org or {}).get("north_star", "") or "(not set)"

                week_start = _get_next_monday().isoformat()
                members = list(members_col.find({"org_id": org_id, "status": "active"}))
                member_list = []
                for mm in members:
                    u = users_col.find_one({"id": mm["user_id"]}, {"_id": 0, "name": 1, "function": 1})
                    member_list.append({"name": (u or {}).get("name", "Member"), "function": (u or {}).get("function", "general")})

                dept_text = "\n".join(
                    f"- {d['function']}: {d['objective']}\n  KRs: {'; '.join(_kr_desc(k) for k in d.get('key_results', [])[:4])}"
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

                r = client().messages.create(model=PRIMARY_MODEL, max_tokens=2000,
                    system=[{"type": "text", "text": TASK_GENERATION_SYSTEM}],
                    messages=[{"role": "user", "content": prompt}])
                txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
                data = json.loads(_extract_json(txt))

                tasks = []
                week_start_dt = datetime.fromisoformat(week_start)
                for t in (data.get("tasks") or [])[:30]:
                    if not isinstance(t, dict) or not t.get("title"):
                        continue
                    func = norm_dep_function(t.get("department_function", "general"))
                    best = _best_member_for_function(org_id, func)
                    dept = next((d for d in (plan.get("departments") or []) if d.get("function") == func), {})
                    dept_krs = dept.get("key_results", [])
                    idx = int(t.get("linked_kr_index", 0)) if dept_krs else -1
                    kr_text = _kr_desc(dept_krs[idx]) if 0 <= idx < len(dept_krs) else ""
                    tasks.append({
                        "id": str(uuid.uuid4()), "org_id": org_id, "plan_id": plan["id"],
                        "department_function": func, "linked_kr_index": int(t.get("linked_kr_index", 0)),
                        "title": str(t.get("title", ""))[:200],
                        "description": str(t.get("description", ""))[:1000],
                        "founder_context": (
                            f"Vision: {north_star}\n"
                            f"→ Company objective: {plan.get('company_objective', '')}\n"
                            f"→ {func}: {dept.get('objective', '')}\n"
                            f"→ KR: {kr_text}"
                        ),
                        "assigned_to": best["user_id"], "assigned_to_name": best["name"],
                        "status": "pending",
                        "due_at": (week_start_dt + timedelta(days=6, hours=23, minutes=59)).isoformat(),
                        "week_start": week_start, "generated_week": week_start_dt.isocalendar()[1],
                        "proof_files": [],
                        "ai_review": {"status": "pending", "notes": "", "confidence": 0.0, "reviewed_at": None},
                        "stage": {"label": "not_started", "confidence": 1.0, "last_updated": now_utc().isoformat()},
                        "escalation": {"dept_head_contacted": False, "dept_head_response": "",
                                       "founder_contacted": False, "founder_response": "", "escalated_at": None},
                        "created_at": now_utc().isoformat(), "updated_at": now_utc().isoformat(), "completed_at": None,
                    })
                if tasks:
                    tasks_col.insert_many(tasks)
                    log.info(f"scheduler: generated {len(tasks)} tasks for org {org_id}")
            except Exception as e:
                log.error(f"scheduler: task generation failed for org {plan.get('org_id')}: {e}")
    except Exception as e:
        log.error(f"scheduler: saturday night run failed: {e}")
    log.info("scheduler: Saturday night task generation complete")


# Periodic job: escalate overdue tasks
def _six_hour_housekeeping():
    log.info("scheduler: 6h housekeeping starting")
    try:
        now = now_utc()
        now_iso = now.isoformat()
        six_hours_later = (now + timedelta(hours=6)).isoformat()
        overdue = list(tasks_col.find({
            "status": {"$nin": ["done", "awaiting_review"]},
            "due_at": {"$lt": now_iso, "$ne": None},
        }))
        for t in overdue:
            if not t.get("escalation", {}).get("dept_head_contacted"):
                tasks_col.update_one({"id": t["id"]}, {"$set": {
                    "escalation.dept_head_contacted": True,
                    "escalation.escalated_at": now_iso,
                }})
        nearing = list(tasks_col.find({
            "status": {"$in": ["pending", "in_progress"]},
            "due_at": {"$gte": now_iso, "$lte": six_hours_later},
        }))
        if nearing:
            log.info(f"scheduler: {len(nearing)} tasks nearing due")
        clarified = list(tasks_col.find({
            "status": "needs_clarification",
            "escalation.dept_head_contacted": True,
        }))
        for t in clarified:
            escalated_at = t.get("escalation", {}).get("escalated_at")
            if escalated_at:
                try:
                    esc_dt = datetime.fromisoformat(escalated_at.replace("Z", "+00:00"))
                    if (now - esc_dt).total_seconds() > 86400 and not t.get("escalation", {}).get("founder_contacted"):
                        tasks_col.update_one({"id": t["id"]}, {"$set": {
                            "escalation.founder_contacted": True,
                        }})
                        log.info(f"scheduler: escalated task {t['id']} to founder")
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        log.error(f"scheduler: 6h housekeeping failed: {e}")


# Weekly job placeholder: Monday digest
def _monday_morning_digest():
    log.info("scheduler: Monday morning digest ready")


def _execute_approved_tasks_cron():
    """Wire 4: execute approved tasks across all orgs."""
    try:
        from execution.bridge import execute_approved_tasks
        for org in orgs_col.find({}, {"_id": 0, "id": 1, "name": 1}):
            try:
                result = execute_approved_tasks(org["id"], max_tasks=5)
                if result.get("executed", 0) > 0:
                    log.info(f"exec_cron: org {org['name']} — executed {result['executed']} tasks")
            except Exception as e:
                log.warning(f"exec_cron: org {org.get('id')} failed — {e}")
    except Exception as e:
        log.exception(f"exec_cron: global failure — {e}")


def _business_os_cron():
    """Autonomous Business OS cycle — agents run, execute through tools, verify, learn."""
    try:
        from business_os import business_cycle_all_orgs
        result = business_cycle_all_orgs()
        count = result.get("orgs_processed", 0)
        if count > 0:
            log.info(f"business_os: {count} orgs processed autonomously")
    except Exception as e:
        log.exception(f"business_os: global failure — {e}")


# Daily job: run morning briefs for orgs
def _morning_brief_cron():
    try:
        from business_os import run_business_process
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1, "name": 1}):
            try:
                run_business_process(org["id"], "morning_brief")
            except Exception:
                pass
    except Exception as e:
        log.exception(f"morning_brief cron failed: {e}")


# Daily job: run midday follow-ups for orgs
def _midday_followup_cron():
    try:
        from business_os import run_business_process
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1, "name": 1}):
            try:
                run_business_process(org["id"], "midday_followup")
            except Exception:
                pass
    except Exception as e:
        log.exception(f"midday_followup cron failed: {e}")


# Daily job: run evening wraps for orgs
def _evening_wrap_cron():
    try:
        from business_os import run_business_process
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1, "name": 1}):
            try:
                run_business_process(org["id"], "evening_wrap")
            except Exception:
                pass
    except Exception as e:
        log.exception(f"evening_wrap cron failed: {e}")


def _weekly_system_scan():
    """Rebuild system model + run signal scan for every org with a strategy set."""
    try:
        from business_system import init_system_model, persist_system_model, run_signal_scan
        from execution.bridge import generate_tasks_for_at_risk_functions
        from okr_engine import refresh_okr_progress_from_scan
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1, "name": 1}):
            try:
                model = init_system_model(org)
                persist_system_model(org["id"], model)
                scan = run_signal_scan(org["id"])
                # Wire 1: generate tasks for at-risk functions
                if scan.get("at_risk_count", 0) > 0:
                    task_ids = generate_tasks_for_at_risk_functions(org["id"])
                    log.info(f"system_scan: org {org['name']} — {scan['at_risk_count']} at-risk, {len(task_ids)} tasks generated")
                else:
                    log.info(f"system_scan: org {org['name']} — all healthy, no tasks needed")
                # Wire 5: refresh OKR progress from execution data
                okr_health = refresh_okr_progress_from_scan(org["id"])
                if okr_health:
                    log.info(f"system_scan: org {org['name']} — OKR health: {okr_health['on_track']}/{okr_health['total_krs']} on track")
            except Exception as e:
                log.warning(f"system_scan: org {org.get('id')} failed — {e}")
    except Exception as e:
        log.exception(f"system_scan: global failure — {e}")

# Register the scheduled jobs
scheduler.add_job(_saturday_night_generate, CronTrigger(day_of_week="sat", hour=22, minute=0, timezone="Asia/Kolkata"))
scheduler.add_job(_monday_morning_digest, CronTrigger(day_of_week="mon", hour=6, minute=0, timezone="Asia/Kolkata"))
scheduler.add_job(_six_hour_housekeeping, IntervalTrigger(hours=6))
scheduler.add_job(_weekly_system_scan, CronTrigger(day_of_week="sat", hour=22, minute=30, timezone="Asia/Kolkata"))
scheduler.add_job(_execute_approved_tasks_cron, IntervalTrigger(hours=3))  # Wire 4: execute approved tasks every 3 hours
scheduler.add_job(_business_os_cron, IntervalTrigger(minutes=15))  # Business OS: autonomous cycle every 15 min
scheduler.add_job(_morning_brief_cron, CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"))
scheduler.add_job(_midday_followup_cron, CronTrigger(hour=14, minute=0, timezone="Asia/Kolkata"))
scheduler.add_job(_evening_wrap_cron, CronTrigger(hour=19, minute=0, timezone="Asia/Kolkata"))
scheduler.add_job(cleanup_expired_sessions, IntervalTrigger(hours=24))  # Session cleanup

# ── SALAAR: The Shadow Agent ──
from salaar import salaar_realtime_scan, salaar_deep_scan, auto_advance_all_chains
scheduler.add_job(salaar_realtime_scan, IntervalTrigger(minutes=5))   # Awareness: scan every 5 min
scheduler.add_job(salaar_deep_scan, IntervalTrigger(minutes=30))        # Deep: people, patterns, health
scheduler.add_job(auto_advance_all_chains, IntervalTrigger(minutes=15))  # Chain auto-advance + verify
from salaar.threats import ensure_salaar_startup
# Revenue jobs: trial conversion + mandate renewal (daily 02:30 IST) + topup status poll is webhook-driven
try:
    from subscriptions import process_pending_trial_conversions, process_mandate_executions
    scheduler.add_job(process_pending_trial_conversions, CronTrigger(hour=2, minute=30, timezone="Asia/Kolkata"))
    scheduler.add_job(process_mandate_executions, CronTrigger(hour=2, minute=35, timezone="Asia/Kolkata"))
except Exception:
    pass

# Autonomous revenue cycle — try to earn on a schedule (honest: tasks are L3-approval, money is real)
def _revenue_cycle_cron():
    try:
        from revenue_engine import run_revenue_cycle
        for org in orgs_col.find({"north_star": {"$ne": "", "$exists": True}}, {"_id": 0, "id": 1}):
            try:
                run_revenue_cycle(org["id"], pipelines=["invoicing", "retention"])
            except Exception:
                pass
        for org in orgs_col.find({"north_star": {"$eq": ""}}, {"_id": 0, "id": 1}):
            # Even without north_star, at least try overdue collection if tools are connected
            try:
                run_revenue_cycle(org["id"], pipelines=["invoicing"])
            except Exception:
                pass
    except Exception as e:
        log.warning(f"revenue_cycle failed: {e}")
scheduler.add_job(_revenue_cycle_cron, IntervalTrigger(hours=6))


# Configure CORS from environment origins
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "")
if not CORS_ORIGINS:
    log.warning("CORS_ORIGINS not set — allowing no cross-origin requests. Set to comma-separated origins for production.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS.split(",") if CORS_ORIGINS else [],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
