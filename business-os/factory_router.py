"""Factory Router — the HTTP surface for idea → business.

  POST /api/factory/build   {idea} -> full build (audit+blueprint+catalog+worth+growth)
  GET  /api/factory/builds  list for org
  GET  /api/factory/builds/{id}
  POST /api/factory/chat    {message} -> if looks_like_business_idea, builds; else 204 + hint

Auth: current_user (org-scoped via members_col). Zoho honesty throughout.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from security import current_user
from db import members_col

router = APIRouter(prefix="/api/factory", tags=["factory"])

def _org_id_for(user: dict) -> Optional[str]:
    m = members_col.find_one({"user_id": user["id"], "status": "active"})
    return m["org_id"] if m else None

class BuildIn(BaseModel):
    idea: str = Field(min_length=8, max_length=4000, description="One sentence: the business you want (e.g. 'fast fashion ecommerce for Gen Z women in India')")
    force: bool = False

@router.post("/build")
def factory_build(body: BuildIn, user: dict = Depends(current_user)):
    org_id = _org_id_for(user)
    if not org_id:
        raise HTTPException(403, "Create a workspace first (Team -> Create workspace)")
    from factory_bridge import build_from_idea
    out = build_from_idea(body.idea, org_id=org_id, user_id=user["id"])
    if not out.get("ok"):
        raise HTTPException(422, out.get("error", "Could not build"))
    return out

@router.get("/builds")
def factory_list_builds(limit: int = 20, user: dict = Depends(current_user)):
    org_id = _org_id_for(user)
    if not org_id:
        return {"builds": []}
    from factory_bridge import list_factory_builds
    return {"builds": list_factory_builds(org_id, limit=min(limit, 50))}

@router.get("/builds/{build_id}")
def factory_get_build(build_id: str, user: dict = Depends(current_user)):
    org_id = _org_id_for(user)
    if not org_id:
        raise HTTPException(403, "No workspace")
    from factory_bridge import get_factory_build
    doc = get_factory_build(build_id, org_id)
    if not doc:
        raise HTTPException(404, "Build not found")
    return {"build": doc}

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

@router.post("/chat")
def factory_chat(body: ChatIn, user: dict = Depends(current_user)):
    """Chat entry point for the factory.

    If `message` looks like a business idea -> builds it and returns the business.
    Otherwise returns {action: 'chat', hint} so the frontend stays on the Deep Discussion thread.
    """
    from factory_bridge import looks_like_business_idea, build_from_idea
    msg = (body.message or "").strip()
    if not looks_like_business_idea(msg):
        return {"action": "chat", "hint": "Not a business idea — continuing your current discussion thread. To build a business, try: 'build a fast fashion ecommerce business' or 'my idea is: ...'"}
    org_id = _org_id_for(user)
    if not org_id:
        raise HTTPException(403, "Create a workspace first (Team -> Create workspace)")
    out = build_from_idea(msg, org_id=org_id, user_id=user["id"])
    if not out.get("ok"):
        raise HTTPException(422, out.get("error", "Could not build"))
    return {"action": "built", **out}
