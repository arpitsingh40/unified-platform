"""Credit ledger + pre-aggregated global stats.
Design for scale: admin overview reads ONE counters doc ($inc-maintained) instead of
scanning collections. Every credit movement is an immutable ledger row (audit trail).
"""
import os
import uuid
import logging
from db import (users_col, threads_col, events_col, telemetry_col, ledger_col,
                stats_col, traffic_col, geo_col, orders_col, feedback_col)
from security import pwd, now_utc

log = logging.getLogger("ledger")

# Founder admin credentials from environment
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "ceo@smartdecigen.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "FounderOS@2026")


def inc_stats(delta: dict):
    """Atomic $inc on the single global counters doc."""
    try:
        stats_col.update_one({"id": "global"}, {"$inc": delta}, upsert=True)
    except Exception as e:
        log.error(f"inc_stats failed: {e}")


# Read the global stats counters doc
def get_stats() -> dict:
    return stats_col.find_one({"id": "global"}) or {}


def record_ledger(user_id: str, entry_type: str, credits: int, **extra):
    """entry_type: free_grant | purchase | turn_spend | admin_grant"""
    try:
        ledger_col.insert_one({"id": str(uuid.uuid4()), "user_id": user_id, "type": entry_type,
                               "credits": credits, "at": now_utc(), **extra})
    except Exception as e:
        log.error(f"record_ledger failed: {e}")


def ensure_startup():
    """Idempotent: indexes, founder account, one-time stats backfill from existing data."""
    # ---- indexes (all admin/list queries are index-backed) ----
    users_col.create_index("id", unique=True)
    users_col.create_index("email", unique=True)
    users_col.create_index([("created_at", -1)])
    threads_col.create_index("thread_id", unique=True)
    threads_col.create_index("user_id")
    events_col.create_index("thread_id")
    events_col.create_index([("user_id", 1), ("action_done", 1)])
    telemetry_col.create_index([("type", 1), ("at", -1)])
    telemetry_col.create_index([("user_id", 1), ("at", -1)])
    ledger_col.create_index([("user_id", 1), ("at", -1)])
    ledger_col.create_index([("type", 1), ("at", -1)])
    traffic_col.create_index("session_id", unique=True)
    traffic_col.create_index([("started_at", -1)])
    traffic_col.create_index([("last_seen_at", -1)])
    traffic_col.create_index("user_id")
    orders_col.create_index("order_id", unique=True)
    orders_col.create_index([("user_id", 1), ("created_at", -1)])
    orders_col.create_index("zoho_session_id")
    geo_col.create_index("ip", unique=True)
    stats_col.create_index("id", unique=True)
    feedback_col.create_index("id", unique=True)
    feedback_col.create_index([("created_at", -1)])
    feedback_col.create_index([("status", 1), ("created_at", -1)])
    feedback_col.create_index([("category", 1), ("created_at", -1)])

    # ---- founder account (idempotent) ----
    existing = users_col.find_one({"email": ADMIN_EMAIL})
    if not existing:
        users_col.insert_one({
            "id": str(uuid.uuid4()), "email": ADMIN_EMAIL, "name": "Founder",
            "password_hash": pwd.hash(ADMIN_PASSWORD), "credits": 1000, "is_admin": True,
            "country": "India", "city": "", "created_at": now_utc(),
            "questions_asked": 0, "tokens_in": 0, "tokens_out": 0,
            "credits_issued_free": 0, "credits_issued_paid": 0,
        })
        log.info(f"founder account created: {ADMIN_EMAIL}")
    elif not existing.get("is_admin"):
        users_col.update_one({"email": ADMIN_EMAIL}, {"$set": {"is_admin": True}})

    # ---- one-time backfill of counters from pre-existing data ----
    if not stats_col.find_one({"id": "global"}):
        signup_credits = int(os.environ.get("SIGNUP_CREDITS", "100"))
        turn_cost = int(os.environ.get("TURN_COST", "5"))
        non_admin = users_col.count_documents({"is_admin": {"$ne": True}})
        questions = telemetry_col.count_documents({"type": "discussion_turn"})
        stats_col.insert_one({
            "id": "global",
            "questions_total": questions, "turns_normal": questions, "turns_ultra": 0,
            "credits_issued_free": signup_credits * non_admin, "credits_issued_paid": 0,
            "credits_spent": turn_cost * questions,
            "tokens_in": 0, "tokens_out": 0,
            "revenue_inr": 0, "purchases_count": 0,
            "subs_active": 0, "subs_trial": 0, "mrr_inr": 0, "subs_revenue_inr": 0,
            "sessions_total": 0, "unique_ips": 0,
        })
        for u in users_col.find({}, {"id": 1, "is_admin": 1, "questions_asked": 1}):
            if u.get("questions_asked") is not None:
                continue
            q = telemetry_col.count_documents({"type": "discussion_turn", "user_id": u["id"]})
            users_col.update_one({"id": u["id"]}, {"$set": {
                "questions_asked": q, "tokens_in": 0, "tokens_out": 0,
                "credits_issued_free": 0 if u.get("is_admin") else signup_credits,
                "credits_issued_paid": 0,
            }})
        log.info("global stats backfilled from existing data")
