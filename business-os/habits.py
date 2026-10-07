"""Habit Tracker — capture, track, streak, identity layer, weekly review.
Backed by habits collection. Each habit has a frequency, streak, identity statement, and log."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import habits_col
from security import current_user, now_utc
from ledger import inc_stats

log = logging.getLogger("habits")
router = APIRouter(prefix="/api/v1/habits")

FREQUENCIES = ("daily", "weekly", "custom")

# Request schema for creating a habit
class HabitCreateIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    frequency: str = "daily"
    identity_statement: str = ""
    notes: str = ""

# Request schema for updating a habit
class HabitUpdateIn(BaseModel):
    title: Optional[str] = None
    frequency: Optional[str] = None
    identity_statement: Optional[str] = None
    notes: Optional[str] = None
    archived: Optional[bool] = None

# Request schema for logging habit completion
class HabitLogIn(BaseModel):
    note: str = ""

# List user's habits with computed views
@router.get("")
def list_habits(user: dict = Depends(current_user)):
    items = list(habits_col.find({"user_id": user["id"]}).sort("created_at", -1))
    now = now_utc()
    out = []
    for h in items:
        out.append(_view(h, now))
    return {"habits": out}

# Create a new habit
@router.post("")
def create_habit(body: HabitCreateIn, user: dict = Depends(current_user)):
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "title": body.title.strip(),
        "frequency": body.frequency if body.frequency in FREQUENCIES else "daily",
        "identity_statement": body.identity_statement.strip(),
        "notes": body.notes.strip(),
        "streak": 0, "longest_streak": 0,
        "total_done": 0,
        "logs": [],
        "archived": False,
        "created_at": now_utc(), "updated_at": now_utc(),
    }
    habits_col.insert_one(doc)
    inc_stats({"habits_created": 1})
    return _view(doc, now_utc())

# Fetch a single habit by ID
@router.get("/{habit_id}")
def get_habit(habit_id: str, user: dict = Depends(current_user)):
    h = habits_col.find_one({"id": habit_id, "user_id": user["id"]})
    if not h:
        raise HTTPException(404, "Habit not found")
    return _view(h, now_utc())

# Update habit fields
@router.patch("/{habit_id}")
def update_habit(habit_id: str, body: HabitUpdateIn, user: dict = Depends(current_user)):
    h = habits_col.find_one({"id": habit_id, "user_id": user["id"]})
    if not h:
        raise HTTPException(404, "Habit not found")
    updates = {"updated_at": now_utc()}
    for field in ("title", "frequency", "identity_statement", "notes"):
        v = getattr(body, field, None)
        if v is not None:
            updates[field] = v
    if body.archived is not None:
        updates["archived"] = body.archived
    habits_col.update_one({"id": habit_id}, {"$set": updates})
    fresh = habits_col.find_one({"id": habit_id})
    return _view(fresh, now_utc())

# Log today's habit completion
@router.post("/{habit_id}/log")
def log_habit(habit_id: str, body: HabitLogIn, user: dict = Depends(current_user)):
    h = habits_col.find_one({"id": habit_id, "user_id": user["id"]})
    if not h:
        raise HTTPException(404, "Habit not found")
    now = now_utc()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # check if already logged today
    if h.get("logs"):
        last_log = h["logs"][-1]
        last_date = (last_log.get("at") if isinstance(last_log.get("at"), datetime)
                     else datetime.fromisoformat(last_log.get("at", "").replace("Z", "+00:00")))
        if last_date.replace(hour=0, minute=0, second=0, microsecond=0) >= today:
            # update instead of duplicate
            habits_col.update_one({"id": habit_id}, {"$set": {
                f"logs.{len(h['logs'])-1}.note": body.note,
                f"logs.{len(h['logs'])-1}.at": now,
                "updated_at": now,
            }})
            fresh = habits_col.find_one({"id": habit_id})
            return _view(fresh, now)
    log_entry = {"at": now, "note": body.note}
    habits_col.update_one({"id": habit_id}, {
        "$push": {"logs": log_entry},
        "$inc": {"total_done": 1},
        "$set": {"updated_at": now},
    })
    # recalculate streak
    fresh = habits_col.find_one({"id": habit_id})
    _recalc_streak(fresh["id"], fresh.get("frequency", "daily"), fresh.get("logs", []))
    fresh = habits_col.find_one({"id": habit_id})
    inc_stats({"habit_logs": 1})
    return _view(fresh, now)

# Delete a habit
@router.delete("/{habit_id}")
def delete_habit(habit_id: str, user: dict = Depends(current_user)):
    r = habits_col.delete_one({"id": habit_id, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Habit not found")
    return {"ok": True}

# Build habit API view with streak stats
def _view(h, now):
    if not h:
        return None
    logs = []
    for l in (h.get("logs") or []):
        at = l.get("at")
        logs.append({"at": at.isoformat() if isinstance(at, datetime) else at, "note": l.get("note", "")})
    days_window = 7 if h.get("frequency") == "daily" else 4
    done_this_window = sum(1 for l in logs if _date_only(l["at"]) >= _date_only(now) - timedelta(days=days_window))
    return {
        "id": h["id"], "title": h["title"],
        "frequency": h.get("frequency", "daily"),
        "identity_statement": h.get("identity_statement", ""),
        "notes": h.get("notes", ""),
        "streak": h.get("streak", 0),
        "longest_streak": h.get("longest_streak", 0),
        "total_done": h.get("total_done", 0),
        "done_today": _is_today(logs, now),
        "done_this_window": done_this_window,
        "logs": logs[-30:],  # last 30 logs
        "archived": h.get("archived", False),
        "created_at": h.get("created_at").isoformat() if isinstance(h.get("created_at"), datetime) else h.get("created_at"),
    }

# Normalize datetime to date-only
def _date_only(dt):
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return datetime.min
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

# Check if habit was logged today
def _is_today(logs, now):
    today = _date_only(now)
    for l in logs:
        if _date_only(l["at"]) == today:
            return True
    return False

# Recompute streak from habit logs
def _recalc_streak(habit_id, frequency, logs):
    if not logs:
        return
    sorted_logs = sorted(logs, key=lambda x: x["at"] if isinstance(x["at"], datetime) else datetime.fromisoformat(x["at"].replace("Z", "+00:00")), reverse=True)
    steps = {"daily": 1, "weekly": 7, "custom": 3}
    gap = steps.get(frequency, 1)
    streak = 0
    today = _date_only(now_utc())
    expected = today
    for l in sorted_logs:
        log_date = _date_only(l["at"] if isinstance(l["at"], datetime) else l["at"])
        if log_date == expected or (streak == 0 and (expected - log_date).days <= 1):
            if streak == 0 and log_date < expected:
                pass
            expected = log_date - timedelta(days=gap)
            streak += 1
        elif log_date < expected:
            break
    current_longest = (habits_col.find_one({"id": habit_id}) or {}).get("longest_streak", 0)
    habits_col.update_one({"id": habit_id}, {"$set": {
        "streak": streak,
        "longest_streak": max(current_longest, streak),
    }})
