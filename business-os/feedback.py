"""User feedback: any signed-in user can submit rating+category+message.
Founder reviews them in Founder OS (status: new -> reviewed -> resolved).
Lists are paginated + index-backed (status/category/created_at indexes in ledger.ensure_startup)."""
import uuid
from typing import Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from pymongo import ReturnDocument
from db import feedback_col
from security import current_user, require_admin, now_utc

router = APIRouter(prefix="/api", tags=["feedback"])

CATEGORIES = ("bug", "idea", "praise", "other")
STATUSES = ("new", "reviewed", "resolved")


# Request schema for submitting feedback
class FeedbackIn(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    category: Literal["bug", "idea", "praise", "other"]
    message: str = Field(..., min_length=1, max_length=2000)


# Request schema for updating feedback status
class FeedbackStatusIn(BaseModel):
    status: Literal["new", "reviewed", "resolved"]


# Strip Mongo fields and ISO-format datetimes
def _clean(doc: dict) -> dict:
    out = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        out[k] = v.isoformat() if hasattr(v, "isoformat") else v
    return out


# ---------------------------------------------------------------- user side
# Submit new feedback from a signed-in user
@router.post("/feedback")
def submit_feedback(body: FeedbackIn, user: dict = Depends(current_user)):
    msg = body.message.strip()
    if not msg:
        raise HTTPException(422, "Message cannot be empty")
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "user_email": user.get("email", ""),
        "user_name": user.get("name", ""),
        "rating": body.rating,
        "category": body.category,
        "message": msg,
        "status": "new",
        "created_at": now_utc(),
    }
    feedback_col.insert_one(doc)
    return {"ok": True, "id": doc["id"]}


# ---------------------------------------------------------------- founder side
# List feedback for founder with filters and summary
@router.get("/admin/feedback")
def list_feedback(page: int = Query(1, ge=1), limit: int = Query(25, ge=1, le=100),
                  status: Optional[str] = Query(None), category: Optional[str] = Query(None),
                  admin: dict = Depends(require_admin)):
    filt = {}
    if status in STATUSES:
        filt["status"] = status
    if category in CATEGORIES:
        filt["category"] = category
    total = feedback_col.count_documents(filt)
    items = [_clean(f) for f in feedback_col.find(filt, {"_id": 0})
             .sort("created_at", -1).skip((page - 1) * limit).limit(limit)]
    # summary: index-backed counts + bounded avg over the 500 most recent entries
    all_total = feedback_col.count_documents({})
    by_status = {s: feedback_col.count_documents({"status": s}) for s in STATUSES}
    by_category = {c: feedback_col.count_documents({"category": c}) for c in CATEGORIES}
    agg = list(feedback_col.aggregate([
        {"$sort": {"created_at": -1}}, {"$limit": 500},
        {"$group": {"_id": None, "avg_rating": {"$avg": "$rating"}}}]))
    summary = {"total": all_total, "by_status": by_status, "by_category": by_category,
               "avg_rating": round(agg[0]["avg_rating"], 2) if agg else 0}
    return {"summary": summary, "items": items, "total": total, "page": page,
            "pages": max(1, -(-total // limit))}


# Update a feedback item's review status
@router.patch("/admin/feedback/{feedback_id}")
def set_feedback_status(feedback_id: str, body: FeedbackStatusIn,
                        admin: dict = Depends(require_admin)):
    res = feedback_col.find_one_and_update(
        {"id": feedback_id},
        {"$set": {"status": body.status, "reviewed_at": now_utc()}},
        return_document=ReturnDocument.AFTER)
    if not res:
        raise HTTPException(404, "Feedback not found")
    return {"ok": True, "item": _clean(res)}
