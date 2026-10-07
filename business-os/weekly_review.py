"""Weekly Review — structured capture → clarify → reflect → plan cycle.
Modeled after GTD weekly review + founder rhythm. Stored per user per week."""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import weekly_reviews_col
from security import current_user, now_utc
from ledger import inc_stats

log = logging.getLogger("weekly_review")
router = APIRouter(prefix="/api/v1/weekly-review")

# Weekly review stage definitions and labels
STAGES = ["capture", "clarify", "reflect", "plan"]
STAGE_LABELS = {
    "capture": "Capture — what happened this week?",
    "clarify": "Clarify — what does it mean?",
    "reflect": "Reflect — what did we learn?",
    "plan": "Plan — what's next?",
}

# Request schema for creating a review
class ReviewCreateIn(BaseModel):
    pass

# Request schema for updating a review
class ReviewUpdateIn(BaseModel):
    stage: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None

# Compute the current ISO week key
def _current_week_key():
    now = now_utc()
    iso = now.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"

# Fetch or create this week's review doc
def _get_or_create(user_id):
    week_key = _current_week_key()
    r = weekly_reviews_col.find_one({"user_id": user_id, "week_key": week_key})
    if not r:
        r = {
            "id": str(uuid.uuid4()), "user_id": user_id,
            "week_key": week_key,
            "stage": "capture",
            "status": "in_progress",
            "content": {"capture": "", "clarify": "", "reflect": "", "plan": ""},
            "created_at": now_utc(), "updated_at": now_utc(),
        }
        weekly_reviews_col.insert_one(r)
        inc_stats({"weekly_reviews_started": 1})
    return r

# Convert review doc to API response shape
def _serialize(r):
    return {
        "id": r["id"], "week_key": r["week_key"],
        "stage": r.get("stage", "capture"),
        "status": r.get("status", "in_progress"),
        "content": r.get("content", {}),
        "stage_label": STAGE_LABELS.get(r.get("stage", "capture"), ""),
        "stages": STAGES,
        "stage_labels": STAGE_LABELS,
        "progress_pct": _progress_pct(r.get("stage", "capture")),
        "created_at": r.get("created_at").isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
        "updated_at": r.get("updated_at").isoformat() if isinstance(r.get("updated_at"), datetime) else r.get("updated_at"),
    }

# Map stage key to completion percentage
def _progress_pct(stage):
    if stage not in STAGES:
        return 0
    return int(100 * STAGES.index(stage) / len(STAGES))

# Return the current week's review
@router.get("")
def get_review(user: dict = Depends(current_user)):
    r = _get_or_create(user["id"])
    return _serialize(r)

# Return recent weekly review history
@router.get("/history")
def review_history(user: dict = Depends(current_user)):
    items = list(weekly_reviews_col.find({"user_id": user["id"]}).sort("week_key", -1).limit(8))
    return {"reviews": [_serialize(r) for r in items]}

# Advance stage or save content for the review
@router.patch("")
def update_review(body: ReviewUpdateIn, user: dict = Depends(current_user)):
    r = _get_or_create(user["id"])
    updates = {"updated_at": now_utc()}
    if body.stage:
        if body.stage not in STAGES:
            raise HTTPException(400, f"Invalid stage: {body.stage}. Must be one of {STAGES}")
        old_content = r.get("content", {})
        if not old_content.get(body.stage, "").strip():
            raise HTTPException(400, f"Complete the {body.stage} section before advancing")
        idx = STAGES.index(body.stage)
        prev = STAGES[idx - 1] if idx > 0 else None
        if prev and not r.get("content", {}).get(prev, "").strip():
            updates["stage"] = prev
        else:
            updates["stage"] = body.stage
    if body.content is not None:
        content = {**r.get("content", {}), **{r.get("stage", "capture"): body.content}}
        updates["content"] = content
        # advance stage automatically when content is saved for current stage
        current_stage = r.get("stage", "capture")
        if body.content.strip():
            idx = STAGES.index(current_stage)
            if idx < len(STAGES) - 1:
                updates["stage"] = STAGES[idx + 1]
            else:
                updates["status"] = "completed"
                inc_stats({"weekly_reviews_completed": 1})
    if body.status:
        updates["status"] = body.status
    weekly_reviews_col.update_one({"id": r["id"]}, {"$set": updates})
    fresh = weekly_reviews_col.find_one({"id": r["id"]})
    return _serialize(fresh)

# Reset the current week's review
@router.post("/reset")
def reset_review(user: dict = Depends(current_user)):
    weekly_reviews_col.delete_one({"user_id": user["id"], "week_key": _current_week_key()})
    r = _get_or_create(user["id"])
    return _serialize(r)
