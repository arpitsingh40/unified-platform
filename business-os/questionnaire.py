"""Post-signup Questionnaire — Dream / Capacity / Advantage / Potential.
Captures 4 short user-context answers and grants a one-time bonus credit pack.
The answers are read by engine.py and injected into the LLM system prompt so
every thread the user opens is grounded in their stated reality.

Endpoints (all auth-required, prefix /api/user):
- GET  /questionnaire          -> current state {completed, answers}
- POST /questionnaire          -> save answers + grant bonus credits (idempotent)
"""
import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from db import users_col
from security import current_user, now_utc
from ledger import record_ledger, inc_stats

router = APIRouter(prefix="/api/user", tags=["user"])
log = logging.getLogger("questionnaire")

# One-time credits awarded for completing questionnaire
BONUS_CREDITS = int(os.environ.get("QUESTIONNAIRE_BONUS_CREDITS", "100"))


# Payload for the four context answers
class QuestionnaireIn(BaseModel):
    dream: str = Field(min_length=3, max_length=2000)
    capacity: str = Field(min_length=3, max_length=2000)
    advantage: str = Field(min_length=3, max_length=2000)
    potential: str = Field(min_length=3, max_length=2000)


# Strip timestamps from stored answers
def _serialize(q: Optional[dict]):
    if not q:
        return None
    out = {k: q.get(k, "") for k in ("dream", "capacity", "advantage", "potential")}
    if q.get("completed_at"):
        out["completed_at"] = q["completed_at"].isoformat() if hasattr(q["completed_at"], "isoformat") else q["completed_at"]
    return out


# Return questionnaire state and bonus size
@router.get("/questionnaire")
def get_questionnaire(user: dict = Depends(current_user)):
    fresh = users_col.find_one({"id": user["id"]}, {"_id": 0, "questionnaire": 1, "questionnaire_completed": 1})
    return {
        "completed": bool(fresh.get("questionnaire_completed")),
        "bonus_credits": BONUS_CREDITS,
        "answers": _serialize(fresh.get("questionnaire")),
    }


@router.post("/questionnaire")
def save_questionnaire(body: QuestionnaireIn, user: dict = Depends(current_user)):
    """Idempotent: bonus credits only awarded on the FIRST completion.
    Subsequent saves update the answers (for future personalization) without re-granting credits."""
    now = now_utc()
    answers = {
        "dream": body.dream.strip(),
        "capacity": body.capacity.strip(),
        "advantage": body.advantage.strip(),
        "potential": body.potential.strip(),
        "completed_at": now,
    }
    # Atomic: only grant credits if questionnaire_completed is not already true.
    updated = users_col.find_one_and_update(
        {"id": user["id"], "questionnaire_completed": {"$ne": True}},
        {"$set": {"questionnaire": answers, "questionnaire_completed": True},
         "$inc": {"credits": BONUS_CREDITS, "credits_issued_free": BONUS_CREDITS}},
        return_document=ReturnDocument.AFTER,
    )
    if updated:
        record_ledger(user["id"], "free_grant", BONUS_CREDITS, reason="questionnaire_bonus")
        inc_stats({"credits_issued_free": BONUS_CREDITS})
        log.info(f"questionnaire bonus +{BONUS_CREDITS} credits granted to user {user['id']}")
        return {
            "credits": updated["credits"],
            "credits_added": BONUS_CREDITS,
            "first_completion": True,
            "answers": _serialize(updated.get("questionnaire")),
        }
    # already completed earlier -> update answers but don't re-grant
    users_col.update_one(
        {"id": user["id"]},
        {"$set": {"questionnaire": answers}},
    )
    fresh = users_col.find_one({"id": user["id"]})
    return {
        "credits": fresh.get("credits", 0),
        "credits_added": 0,
        "first_completion": False,
        "answers": _serialize(fresh.get("questionnaire")),
    }
