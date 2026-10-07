"""Layer 3 (virality): shareable Decision Cards + second opinions + founder referrals.

- A founder shares their decision package as a beautiful public card (/d/<share_id>).
  The card carries the decision, odds, trade-offs and confidence, plus a signup CTA,
  so sharp thinking spreads founder-to-founder.
- Any signed-in founder (not the owner) can leave ONE "second opinion" on a card.
- Every user has a referral code; a signup carrying ?ref=<code> grants both sides
  REFERRAL_BONUS credits (handled in server.py signup).

No LLM, no credits spent here. All endpoints are cheap and index-backed.
"""
import os
import uuid
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from db import users_col, journeys_col, shares_col
from security import current_user, now_utc

log = logging.getLogger("share")
router = APIRouter(prefix="/api/share")
referral_router = APIRouter(prefix="/api/referral")

# Credits granted to referrer and referee on signup.
REFERRAL_BONUS = int(os.environ.get("REFERRAL_BONUS", "25"))


# Extract a display-safe first name for public cards.
def _first_name(name, email):
    n = (name or "").strip()
    if n:
        return n.split()[0][:24]
    return (email or "founder").split("@")[0][:24]


def _card_snapshot(direction, reasoning):
    """Public-safe snapshot of a decision package. Never includes the raw conversation,
    the founder model, hidden_desire, or anything identifying beyond a first name."""
    d = direction or {}
    from journey import _decision_confidence  # local import avoids any cycle at module load
    return {
        "decision": d.get("decision", ""),
        "goal": d.get("goal", ""),
        "highest_leverage": d.get("highest_leverage", ""),
        "success_probability": d.get("success_probability", 0),
        "probability_rationale": d.get("probability_rationale", ""),
        "trade_offs": (d.get("trade_offs") or [])[:4],
        "risks": (d.get("risks") or [])[:3],
        "first_moves": (d.get("first_moves") or [])[:4],
        "confidence": _decision_confidence(reasoning),
    }


# Request body for posting a second opinion.
class OpinionIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


@router.post("/direction")
def share_direction(user: dict = Depends(current_user)):
    """Create (or refresh) the caller's public Decision Card from their current direction.
    One card per user: re-sharing refreshes the snapshot but keeps the link stable."""
    j = journeys_col.find_one({"user_id": user["id"]})
    if not j or not j.get("direction"):
        raise HTTPException(400, "Shape a direction first, then share it.")
    snapshot = _card_snapshot(j.get("direction"), j.get("reasoning"))
    existing = shares_col.find_one({"user_id": user["id"], "type": "direction"})
    if existing:
        shares_col.update_one({"id": existing["id"]}, {"$set": {
            "card": snapshot, "founder_name": _first_name(user.get("name"), user.get("email")),
            "updated_at": now_utc()}})
        share_id = existing["id"]
        views = existing.get("views", 0)
    else:
        share_id = uuid.uuid4().hex[:10]
        shares_col.insert_one({
            "id": share_id, "user_id": user["id"], "type": "direction",
            "founder_name": _first_name(user.get("name"), user.get("email")),
            "card": snapshot, "views": 0, "opinions": [],
            "created_at": now_utc(), "updated_at": now_utc()})
        views = 0
    return {"share_id": share_id, "path": f"/d/{share_id}", "views": views}


@router.get("/{share_id}")
def get_card(share_id: str):
    """PUBLIC, no auth. Returns the Decision Card and counts the view."""
    doc = shares_col.find_one_and_update(
        {"id": share_id}, {"$inc": {"views": 1}})
    if not doc:
        raise HTTPException(404, "This decision card does not exist or was removed.")
    return {
        "id": doc["id"],
        "founder_name": doc.get("founder_name", "A founder"),
        "card": doc.get("card") or {},
        "views": doc.get("views", 0) + 1,
        "opinions": [{"name": o.get("name", ""), "text": o.get("text", ""),
                      "at": o.get("at").isoformat() if hasattr(o.get("at"), "isoformat") else o.get("at")}
                     for o in (doc.get("opinions") or [])],
        "created_at": doc.get("created_at").isoformat() if hasattr(doc.get("created_at"), "isoformat") else None,
    }


@router.post("/{share_id}/opinion")
def add_opinion(share_id: str, body: OpinionIn, user: dict = Depends(current_user)):
    """A signed-in founder leaves ONE second opinion on someone else's card
    (posting again replaces their previous take)."""
    doc = shares_col.find_one({"id": share_id})
    if not doc:
        raise HTTPException(404, "This decision card does not exist or was removed.")
    if doc.get("user_id") == user["id"]:
        raise HTTPException(400, "You cannot leave a second opinion on your own decision.")
    text = body.text.strip()
    opinions = [o for o in (doc.get("opinions") or []) if o.get("user_id") != user["id"]]
    opinions.append({"user_id": user["id"], "name": _first_name(user.get("name"), user.get("email")),
                     "text": text, "at": now_utc()})
    opinions = opinions[-50:]
    shares_col.update_one({"id": share_id}, {"$set": {"opinions": opinions, "updated_at": now_utc()}})
    return {"opinions": [{"name": o.get("name", ""), "text": o.get("text", "")} for o in opinions]}


@router.delete("/{share_id}")
def revoke_card(share_id: str, user: dict = Depends(current_user)):
    """Owner removes their public card (the link dies immediately)."""
    r = shares_col.delete_one({"id": share_id, "user_id": user["id"]})
    if r.deleted_count == 0:
        raise HTTPException(404, "Card not found")
    return {"removed": True}


# ----------------------------------------------------------------- referrals
@referral_router.get("")
def my_referral(user: dict = Depends(current_user)):
    """The caller's referral code + live stats. Code is created lazily, once, and is stable."""
    code = user.get("referral_code")
    if not code:
        for _ in range(5):
            candidate = uuid.uuid4().hex[:8]
            try:
                users_col.update_one({"id": user["id"], "referral_code": {"$exists": False}},
                                     {"$set": {"referral_code": candidate}})
                fresh = users_col.find_one({"id": user["id"]}, {"referral_code": 1})
                code = (fresh or {}).get("referral_code")
                if code:
                    break
            except DuplicateKeyError:
                continue
        if not code:
            raise HTTPException(500, "Could not create a referral code, please retry.")
    invited = users_col.count_documents({"referred_by": user["id"]})
    return {"code": code, "path": f"/auth?ref={code}", "invited_count": invited,
            "credits_earned": invited * REFERRAL_BONUS, "bonus": REFERRAL_BONUS}


def ensure_share_startup():
    """Idempotent indexes for the virality layer."""
    shares_col.create_index("id", unique=True)
    shares_col.create_index([("user_id", 1), ("type", 1)])
    users_col.create_index("referral_code", unique=True, sparse=True)
    users_col.create_index("referred_by", sparse=True)
