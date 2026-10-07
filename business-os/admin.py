"""Founder OS API - admin-only (ceo@smartdecigen.com).
Every list is paginated + index-backed; summaries read pre-aggregated counters,
so these endpoints stay O(1)/O(page) even at millions of users."""
import os
import re
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from db import (
    users_col, threads_col, telemetry_col, ledger_col, traffic_col, orders_col,
    conversation_memory_col, user_patterns_col, decisions_col,
)
from security import require_admin, now_utc
from ledger import get_stats

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ----------------------------------------------------------------- model pricing
# USD per 1M tokens. Gemini Flash is free via AI Studio free tier.
# All values overridable via env so the founder can retune without a code change.
# so the founder can retune without a code change.
def _f(env_key: str, default: float) -> float:
    try:
        return float(os.environ.get(env_key, default))
    except (TypeError, ValueError):
        return default

USD_TO_INR = _f("USD_TO_INR", 83.0)

# {model_id: (input_usd_per_M, output_usd_per_M, label)}
MODEL_PRICING = {
    "deepseek-flash": (_f("PRICE_FLASH_IN", 0.0), _f("PRICE_FLASH_OUT", 0.0), "Standard Engine"),
    "deepseek-v4-pro": (_f("PRICE_PRO_IN", 0.0), _f("PRICE_PRO_OUT", 0.0), "Ultra Engine"),
}
UNKNOWN_PRICING = (_f("PRICE_UNKNOWN_IN", 15.0), _f("PRICE_UNKNOWN_OUT", 75.0), "Pro Engine")


# Convert model token usage into an estimated INR cost.
def _price_inr(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out, _ = MODEL_PRICING.get(model, UNKNOWN_PRICING)
    usd = (tokens_in / 1_000_000.0) * p_in + (tokens_out / 1_000_000.0) * p_out
    return round(usd * USD_TO_INR, 2)

# User projection excluding sensitive fields for admin listings.
USER_PROJ = {"_id": 0, "password_hash": 0}


# Serialize datetime values to ISO strings if present.
def _iso(v):
    return v.isoformat() if hasattr(v, "isoformat") else v


# Strip _id and ISO-format datetimes for safe JSON output.
def _clean(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        out[k] = _iso(v) if hasattr(v, "isoformat") else v
    return out


# Dashboard summary: users, engine, credits, tokens, revenue, traffic.
@router.get("/overview")
def overview(admin: dict = Depends(require_admin)):
    s = get_stats()
    now = now_utc()
    week_ago = now - timedelta(days=7)
    day_ago = now - timedelta(days=1)
    users_total = users_col.count_documents({})
    users_7d = users_col.count_documents({"created_at": {"$gte": week_ago}})
    questions_7d = telemetry_col.count_documents({"type": "discussion_turn", "at": {"$gte": week_ago}})
    sessions_7d = traffic_col.count_documents({"started_at": {"$gte": week_ago}})
    active_now = traffic_col.count_documents({"last_seen_at": {"$gte": now - timedelta(minutes=3)}})
    # avg session time over the most recent 500 sessions (bounded work)
    agg = list(traffic_col.aggregate([
        {"$sort": {"started_at": -1}}, {"$limit": 500},
        {"$group": {"_id": None, "avg_s": {"$avg": "$duration_s"}, "total_s": {"$sum": "$duration_s"}}}]))
    avg_s = round(agg[0]["avg_s"]) if agg and agg[0].get("avg_s") is not None else 0
    issued_free = s.get("credits_issued_free", 0)
    issued_paid = s.get("credits_issued_paid", 0)
    spent = s.get("credits_spent", 0)
    return {
        "users": {"total": users_total, "new_7d": users_7d,
                  "active_24h": users_col.count_documents({"last_active_at": {"$gte": day_ago}})},
        "engine": {"questions_total": s.get("questions_total", 0),
                   "turns_normal": s.get("turns_normal", 0),
                   "turns_ultra": s.get("turns_ultra", 0),
                   "questions_7d": questions_7d},
        "credits": {"issued_total": issued_free + issued_paid, "issued_free": issued_free,
                    "issued_paid": issued_paid, "spent": spent,
                    "outstanding": issued_free + issued_paid - spent},
        "tokens": {"input_total": s.get("tokens_in", 0), "output_total": s.get("tokens_out", 0)},
        "revenue": {"total_inr": s.get("revenue_inr", 0), "purchases": s.get("purchases_count", 0)},
        "traffic": {"sessions_total": s.get("sessions_total", 0), "unique_ips": s.get("unique_ips", 0),
                    "sessions_7d": sessions_7d, "avg_session_s": avg_s, "active_now": active_now},
    }


# Paginated admin user list with optional search filter.
@router.get("/users")
def list_users(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
               q: str = Query(""), admin: dict = Depends(require_admin)):
    filt = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        filt = {"$or": [{"email": rx}, {"name": rx}, {"country": rx}]}
    total = users_col.count_documents(filt)
    items = [_clean(u) for u in users_col.find(filt, USER_PROJ)
             .sort("created_at", -1).skip((page - 1) * limit).limit(limit)]
    return {"items": items, "total": total, "page": page, "pages": max(1, -(-total // limit))}


# Full activity dump for one user: threads, Q&A, ledger.
@router.get("/users/{user_id}/activity")
def user_activity(user_id: str, admin: dict = Depends(require_admin)):
    u = users_col.find_one({"id": user_id}, USER_PROJ)
    if not u:
        raise HTTPException(404, "User not found")
    threads = []
    for t in threads_col.find({"user_id": user_id}).sort("opened_at", -1).limit(50):
        qa, pending = [], None
        for m in t.get("messages", []):
            if m.get("role") == "user":
                pending = m
            elif m.get("role") == "engine" and pending is not None:
                qa.append({"question": pending.get("text", ""), "reply": m.get("text", ""),
                           "intent": pending.get("intent"), "at": _iso(m.get("at"))})
                pending = None
        threads.append({"thread_id": t["thread_id"], "goal": t.get("goal", ""),
                        "status": t.get("status", ""), "opened_at": _iso(t.get("opened_at")), "qa": qa})
    ledger = [_clean(entry) for entry in ledger_col.find({"user_id": user_id}).sort("at", -1).limit(50)]
    return {"user": _clean(u), "threads": threads, "ledger": ledger}


# Paginated session traffic list with aggregate summary.
@router.get("/traffic")
def traffic(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
            admin: dict = Depends(require_admin)):
    s = get_stats()
    total = traffic_col.count_documents({})
    items = [_clean(t) for t in traffic_col.find({}, {"_id": 0})
             .sort("started_at", -1).skip((page - 1) * limit).limit(limit)]
    agg = list(traffic_col.aggregate([
        {"$sort": {"started_at": -1}}, {"$limit": 500},
        {"$group": {"_id": None, "avg_s": {"$avg": "$duration_s"}, "total_s": {"$sum": "$duration_s"}}}]))
    _avg_s = agg[0].get("avg_s") if agg else None
    summary = {"sessions_total": total, "unique_ips": s.get("unique_ips", 0),
               "avg_session_s": round(_avg_s) if _avg_s is not None else 0,
               "time_recent_500_s": agg[0]["total_s"] if agg else 0,
               "active_now": traffic_col.count_documents({"last_seen_at": {"$gte": now_utc() - timedelta(minutes=3)}})}
    return {"summary": summary, "items": items, "total": total, "page": page,
            "pages": max(1, -(-total // limit))}


# Credit, token, turn, and revenue usage summary per user.
@router.get("/usage")
def usage(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
          admin: dict = Depends(require_admin)):
    s = get_stats()
    issued_free = s.get("credits_issued_free", 0)
    issued_paid = s.get("credits_issued_paid", 0)
    summary = {
        "credits": {"issued_total": issued_free + issued_paid, "issued_free": issued_free,
                    "issued_paid": issued_paid, "spent": s.get("credits_spent", 0),
                    "outstanding": issued_free + issued_paid - s.get("credits_spent", 0)},
        "tokens": {"input_total": s.get("tokens_in", 0), "output_total": s.get("tokens_out", 0)},
        "turns": {"total": s.get("questions_total", 0), "normal": s.get("turns_normal", 0),
                  "ultra": s.get("turns_ultra", 0)},
        "revenue": {"total_inr": s.get("revenue_inr", 0), "purchases": s.get("purchases_count", 0)},
    }
    total = users_col.count_documents({})
    proj = {"_id": 0, "id": 1, "email": 1, "name": 1, "country": 1, "credits": 1,
            "questions_asked": 1, "tokens_in": 1, "tokens_out": 1,
            "credits_issued_free": 1, "credits_issued_paid": 1, "created_at": 1, "last_active_at": 1}
    items = [_clean(u) for u in users_col.find({}, proj)
             .sort([("questions_asked", -1), ("created_at", -1)]).skip((page - 1) * limit).limit(limit)]
    return {"summary": summary, "items": items, "total": total, "page": page,
            "pages": max(1, -(-total // limit))}


@router.get("/usage/models")
def usage_by_model(admin: dict = Depends(require_admin)):
    """Per-model token + cost + margin breakdown. Reads telemetry_col (one doc
    per LLM call), so the snapshot is always live and matches reality.
    Note: estimated_inr is illustrative only — actual Anthropic billing is
    authoritative. Tune via env vars PRICE_OPUS_IN/OUT, PRICE_HAIKU_IN/OUT,
    PRICE_FABLE_IN/OUT, USD_TO_INR."""
    pipeline = [
        {"$match": {"type": {"$in": ["discussion_turn", "action_assist"]},
                    "model": {"$ne": None}}},
        {"$group": {
            "_id": "$model",
            "turns": {"$sum": 1},
            "tokens_in": {"$sum": {"$ifNull": ["$tokens_in", 0]}},
            "tokens_out": {"$sum": {"$ifNull": ["$tokens_out", 0]}},
            "credits": {"$sum": {"$ifNull": ["$cost", 0]}},
        }},
        {"$sort": {"turns": -1}},
    ]
    rows = list(telemetry_col.aggregate(pipeline))
    items = []
    total_in_tokens = 0
    total_out_tokens = 0
    total_credits_spent = 0
    total_api_inr = 0.0
    for r in rows:
        model = r["_id"] or "unknown"
        ti = int(r.get("tokens_in") or 0)
        to = int(r.get("tokens_out") or 0)
        inr = _price_inr(model, ti, to)
        _, _, label = MODEL_PRICING.get(model, UNKNOWN_PRICING)
        items.append({
            "model": model,
            "label": label,
            "turns": int(r.get("turns") or 0),
            "tokens_in": ti,
            "tokens_out": to,
            "credits_spent": int(r.get("credits") or 0),
            "estimated_inr": inr,
        })
        total_in_tokens += ti
        total_out_tokens += to
        total_credits_spent += int(r.get("credits") or 0)
        total_api_inr += inr

    s = get_stats()
    revenue_inr = float(s.get("revenue_inr", 0) or 0)
    margin_inr = round(revenue_inr - total_api_inr, 2)
    margin_pct = round((margin_inr / revenue_inr) * 100, 1) if revenue_inr > 0 else None

    # pricing table the UI uses for transparency
    pricing = [{"model": m, "label": lbl, "input_usd_per_m": p_in, "output_usd_per_m": p_out}
               for m, (p_in, p_out, lbl) in MODEL_PRICING.items()]

    return {
        "items": items,
        "totals": {
            "turns": sum(i["turns"] for i in items),
            "tokens_in": total_in_tokens,
            "tokens_out": total_out_tokens,
            "credits_spent": total_credits_spent,
            "estimated_api_inr": round(total_api_inr, 2),
            "revenue_inr": revenue_inr,
            "margin_inr": margin_inr,
            "margin_pct": margin_pct,
        },
        "pricing": pricing,
        "usd_to_inr": USD_TO_INR,
    }


# Paginated list of all purchase orders.
@router.get("/purchases")
def purchases(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
              admin: dict = Depends(require_admin)):
    total = orders_col.count_documents({})
    items = [_clean(o) for o in orders_col.find({}, {"_id": 0, "status_history": 0})
             .sort("created_at", -1).skip((page - 1) * limit).limit(limit)]
    return {"items": items, "total": total, "page": page, "pages": max(1, -(-total // limit))}


# ------------------------------------------------------------------------ Conversations / Data section

# Projection for conversation views excluding sensitive fields.
USER_PROJ_CONV = {"_id": 0, "password_hash": 0}


@router.get("/conversations")
def list_conversations(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
                       q: str = Query(""), admin: dict = Depends(require_admin)):
    """Return all threads organised per user — a book/chapter/topic structure.
    Each user is a *chapter*, each of their threads is a *topic*."""
    users_filter = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        users_filter = {"$or": [{"email": rx}, {"name": rx}]}
    total_users = users_col.count_documents(users_filter)
    user_cursor = users_col.find(users_filter, USER_PROJ_CONV).sort("created_at", -1).skip((page - 1) * limit).limit(limit)

    chapters = []
    total_threads = 0
    for u in user_cursor:
        threads = list(threads_col.find({"user_id": u["id"]}).sort("opened_at", -1).limit(100))
        total_threads += len(threads)
        thread_list = []
        for t in threads:
            msgs = t.get("messages", [])
            msg_count = len(msgs)
            user_msg = next((m for m in reversed(msgs) if m.get("role") == "user"), None)
            thread_list.append({
                "thread_id": t["thread_id"],
                "goal": t.get("goal", ""),
                "status": t.get("status", ""),
                "phase": t.get("current_phase", ""),
                "message_count": msg_count,
                "turn_count": sum(1 for m in msgs if m.get("role") == "user"),
                "opened_at": _iso(t.get("opened_at")),
                "last_turn_at": _iso(t.get("last_turn_at")),
                "preview": (user_msg.get("text", "")[:200] if user_msg else ""),
            })
        chapters.append({
            "user": _clean(u),
            "threads": thread_list,
        })
    return {
        "chapters": chapters,
        "total_users": total_users,
        "total_threads": total_threads,
        "page": page,
        "pages": max(1, -(-total_users // limit)),
    }


@router.post("/conversations/memory/refresh")
def refresh_conversation_memory(admin: dict = Depends(require_admin)):
    """Enrich conversation_memory from ALL existing learning systems:
    - users.understanding (living memory)
    - user_patterns_col (behavioral patterns, understanding/substrate history)
    - decisions_col (decision outcomes, commitments, calibration)
    - events_col (emotional/substrate trends)
    - threads_col (goals, state summaries)
    """
    now = now_utc()
    processed = 0
    for u in users_col.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1, "understanding": 1}):
        uid = u["id"]
        threads = list(threads_col.find({"user_id": uid}).sort("opened_at", -1))
        if not threads:
            continue

        # ---- Threads ----
        goals = []
        insights = []
        total_messages = 0
        active_threads = 0
        for t in threads:
            status = t.get("status", "")
            goals.append({"goal": t.get("goal", ""), "status": status,
                          "opened_at": _iso(t.get("opened_at"))})
            if status == "active":
                active_threads += 1
            msgs = t.get("messages", [])
            total_messages += len(msgs)
            for m in msgs:
                if m.get("role") == "engine":
                    text = m.get("text", "")
                    if len(text) > 100:
                        insights.append(text[:300])

        # ---- Understanding (living memory from engine) ----
        understanding = u.get("understanding") or {}

        # ---- Patterns from user_patterns_col ----
        pat_doc = user_patterns_col.find_one({"user_id": uid}) or {}
        patterns = pat_doc.get("patterns") or {}
        total_turns = pat_doc.get("total_turns", 0)
        vulnerability_count = pat_doc.get("vulnerability_count", 0)
        understanding_history = pat_doc.get("understanding_history", []) or []
        substrate_history = pat_doc.get("substrate_history", []) or []

        # Compute pattern trend from history
        pattern_history = []
        if patterns and patterns.get("pattern_type"):
            pattern_history.append({
                "pattern_type": patterns["pattern_type"],
                "confidence": patterns.get("confidence", 0),
                "observation": patterns.get("observation"),
            })

        # Compute fear evolution from understanding_history
        fear_evolution = []
        for uh in (understanding_history or [])[-20:]:
            if isinstance(uh, dict) and uh.get("fears", "").strip():
                fear_evolution.append(uh["fears"][:200])

        # Compute engagement trends from substrate_history
        temps = []
        consistencies = []
        paces = []
        for sh in (substrate_history or [])[-50:]:
            if isinstance(sh, dict):
                et = sh.get("emotional_temperature")
                ec = sh.get("execution_consistency")
                if et is not None:
                    temps.append(float(et))
                if ec is not None:
                    consistencies.append(float(ec))
                pc = sh.get("pace_calibration")
                if pc:
                    paces.append(pc)

        avg_temp = round(sum(temps) / len(temps), 2) if temps else None
        avg_consistency = round(sum(consistencies) / len(consistencies), 2) if consistencies else None
        recent_paces = paces[-10:] if paces else []
        pace_trend = "stable"
        if recent_paces:
            improving = sum(1 for p in recent_paces if p in ("ahead", "on-track"))
            declining = sum(1 for p in recent_paces if p == "behind")
            if improving > declining * 2:
                pace_trend = "improving"
            elif declining > improving * 2:
                pace_trend = "declining"

        # ---- Decisions from decisions_col ----
        dec_total = decisions_col.count_documents({"user_id": uid})
        dec_committed = decisions_col.count_documents({"user_id": uid, "committed_action": {"$exists": True, "$ne": ""}})
        dec_done = decisions_col.count_documents({"user_id": uid, "status": "done"})
        dec_dropped = decisions_col.count_documents({"user_id": uid, "status": "dropped"})

        # Outcome distribution
        outcome_pipeline = [
            {"$match": {"user_id": uid, "outcome.status": {"$in": ["success", "partial", "failed"]}}},
            {"$group": {"_id": "$outcome.status", "count": {"$sum": 1}}},
        ]
        outcome_counts = {r["_id"]: r["count"] for r in decisions_col.aggregate(outcome_pipeline)}

        # Recent decisions with outcomes for the memory view
        recent_decisions = []
        for d in decisions_col.find(
            {"user_id": uid},
            {"_id": 0, "question": 1, "answer": 1, "committed_action": 1, "status": 1,
             "outcome": 1, "impact_inr": 1, "created_at": 1, "mode": 1}
        ).sort("created_at", -1).limit(5):
            recent_decisions.append(_clean(d))

        # Build the enriched memory document
        memory_doc = {
            "user_id": uid,
            "user_name": u.get("name") or u.get("email", ""),
            "email": u.get("email", ""),
            "last_updated": _iso(now),
            "extracted_at": _iso(now),

            # Threads summary
            "threads": {
                "total": len(threads),
                "active": active_threads,
                "total_messages": total_messages,
                "goals": goals,
            },

            # Understanding (living memory from the engine)
            "understanding": {
                "current": {k: understanding.get(k, "") for k in (
                    "focus", "fears", "blockers", "constraints", "tried",
                    "motivators", "stage", "gap_to_goal", "emotional_read", "needs_now"
                )},
                "fear_evolution": fear_evolution,
            },

            # Behavioral patterns
            "patterns": {
                "current": patterns,
                "history": pattern_history,
                "total_turns": total_turns,
                "vulnerability_count": vulnerability_count,
            },

            # Decision outcomes
            "decisions": {
                "total": dec_total,
                "committed": dec_committed,
                "done": dec_done,
                "dropped": dec_dropped,
                "outcomes": outcome_counts,
                "recent": recent_decisions,
            },

            # Engagement / emotional trends
            "engagement": {
                "emotional_temperature_avg": avg_temp,
                "execution_consistency_avg": avg_consistency,
                "pace_trend": pace_trend,
            },

            # Raw insights from engine responses
            "insights": insights[:50],
        }

        conversation_memory_col.update_one(
            {"user_id": uid},
            {"$set": memory_doc},
            upsert=True,
        )
        processed += 1
    return {"processed": processed, "message": f"Memory refreshed for {processed} users"}


@router.get("/conversations/memory")
def get_conversation_memory(q: str = Query(""), admin: dict = Depends(require_admin)):
    """Retrieve enriched long-term memory per user — aggregated from
    understanding, patterns, decisions, engagement, and threads."""
    filt = {}
    if q.strip():
        rx = {"$regex": re.escape(q.strip()), "$options": "i"}
        filt = {"$or": [{"user_name": rx}, {"email": rx}, {"user_id": rx}]}
    items = [_clean(m) for m in conversation_memory_col.find(filt).sort("user_name", 1).limit(200)]
    return {"items": items, "total": len(items)}


@router.get("/conversations/{thread_id}")
def get_conversation_thread(thread_id: str, admin: dict = Depends(require_admin)):
    """Full thread detail with every message."""
    t = threads_col.find_one({"thread_id": thread_id})
    if not t:
        raise HTTPException(404, "Thread not found")
    u = users_col.find_one({"id": t["user_id"]}, USER_PROJ_CONV)
    messages = []
    for m in t.get("messages", []):
        messages.append({
            "role": m.get("role"),
            "text": m.get("text", ""),
            "at": _iso(m.get("at")),
            "intent": m.get("intent"),
        })
    return {
        "thread": {
            "thread_id": t["thread_id"],
            "goal": t.get("goal", ""),
            "why_now": t.get("why_now", ""),
            "status": t.get("status", ""),
            "phase": t.get("current_phase", ""),
            "opened_at": _iso(t.get("opened_at")),
            "last_turn_at": _iso(t.get("last_turn_at")),
            "messages": messages,
            "snapshot_at_last_turn": t.get("snapshot_at_last_turn"),
            "rolling": t.get("rolling"),
        },
        "user": _clean(u) if u else None,
    }
