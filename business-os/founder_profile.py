"""Founder Profile - a deep, connected onboarding conversation that teaches the Decision Brain
WHO the founder is (personality + working style) and WHAT their industry really is.

The distilled profile is stored on the org (owner-only) and injected into every Brain answer via
decision_brain._founder_profile_block (owner asks) + _industry_block (org-wide), so advice fits the
person and is grounded in the real domain instead of generic business talk.

No member ever sees this. One LLM call per interview turn + one to distill.
"""
import os
import json
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from db import orgs_col, members_col
from security import current_user, now_utc
from engine import client, _extract_json

log = logging.getLogger("founder")
router = APIRouter(prefix="/api/founder", tags=["founder-profile"])

# Model list and interview length config
INTERVIEW_MODELS = (os.environ.get("LLM_MODEL", "deepseek-flash").strip(),)
INTERVIEW_TURNS = int(os.environ.get("FOUNDER_INTERVIEW_TURNS", "6"))  # founder answers before auto-distill
MIN_FINISH_ANSWERS = 2  # can finish early after this many answers

# Fixed opening interview question
OPENING_Q = ("To give you advice that genuinely fits you, I want to understand you and your business first. "
             "Tell me in your own words: what does your company do, what stage are you at, and what is the "
             "hardest part of your week right now?")

# Fields the distilled profile contains
PROFILE_FIELDS = ("summary", "personality", "working_style", "communication_style",
                  "decision_style", "risk_appetite", "strengths", "blind_spots",
                  "motivations", "industry_summary")


# ---------------------------------------------------------------- helpers
# Ensure caller is workspace owner
def _require_owner(user: dict) -> dict:
    m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
    if not m:
        raise HTTPException(403, "Only the workspace owner can set up the founder profile.")
    org = orgs_col.find_one({"id": m["org_id"]})
    if not org:
        raise HTTPException(404, "Organization not found")
    return org


# Render interview Q&A as text
def _transcript_text(transcript: list) -> str:
    lines = []
    for i, t in enumerate(transcript, 1):
        lines.append(f"Q{i} (brain): {t.get('q', '')}")
        lines.append(f"A{i} (founder): {t.get('a', '')}")
    return "\n".join(lines)


# One LLM call returning raw text
def _llm_text(system: str, user_msg: str, max_tokens: int = 400) -> str:
    last_err = None
    for model in INTERVIEW_MODELS:
        try:
            r = client().messages.create(
                model=model, max_tokens=max_tokens,
                system=[{"type": "text", "text": system}],
                messages=[{"role": "user", "content": user_msg}],
            )
            return next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        except Exception as e:
            last_err = e
    raise RuntimeError(f"interview LLM failed: {last_err}")


# Prompt that generates the next question
NEXT_Q_SYSTEM = (
    "You are conducting a warm, sharp onboarding interview with a startup founder so an AI advisor can "
    "learn how they operate and what their industry really is. Ask exactly ONE question at a time. Build "
    "directly on what they just said (stay connected, go one level deeper, never repeat). Across the whole "
    "interview you need to cover: their specific industry and market reality, what they sell and their real "
    "edge, how they make hard decisions, their risk appetite, their genuine strengths, their blind spots or "
    "what drains them, and how they like advice delivered. Keep the question short, human, and specific to "
    "their last answer. Plain English. No preamble, no numbering, no quotes. Return ONLY the next question."
)

# Prompt that distills the final profile
DISTILL_SYSTEM = (
    "From this onboarding interview, distill a concise FOUNDER PROFILE an AI advisor will use to tailor every "
    "decision to this person and their industry. Return ONLY valid JSON (no markdown fences) with these keys, "
    "each a short plain-English phrase or 1-2 sentences (empty string if truly unknown): "
    '{"summary": "one vivid sentence capturing who they are as an operator", '
    '"personality": "", "working_style": "", "communication_style": "", "decision_style": "", '
    '"risk_appetite": "", "strengths": "", "blind_spots": "", "motivations": "", '
    '"industry_summary": "2-3 sentences on their SPECIFIC industry/market: sector, segment, geography, business '
    'model, and the real dynamics, players, and constraints that matter"}. Be specific, never generic.'
)


# Ask the next connected question
def _next_question(transcript: list) -> str:
    q = _llm_text(NEXT_Q_SYSTEM, _transcript_text(transcript) + "\n\nNext question:", max_tokens=200)
    q = q.strip().strip('"').strip()
    return q[:600] or "What else should I understand about how you like to work?"


# Distill transcript into founder profile
def _distill(transcript: list) -> dict:
    txt = _llm_text(DISTILL_SYSTEM, _transcript_text(transcript), max_tokens=900)
    try:
        data = json.loads(_extract_json(txt))
    except Exception as e:
        log.warning(f"founder distill parse failed: {e}")
        data = {}
    prof = {k: (str(data.get(k, "")).strip()[:600] if data.get(k) else "") for k in PROFILE_FIELDS}
    if not prof["summary"]:
        prof["summary"] = "A founder who is building deliberately and wants advice that fits how they actually operate."
    return prof


# Client-safe profile and interview state
def _profile_view(org: dict) -> dict:
    fp = org.get("founder_profile") or {}
    iv = org.get("founder_interview") or {}
    return {
        "has_profile": bool(isinstance(fp, dict) and fp.get("summary")),
        "profile": fp if isinstance(fp, dict) else {},
        "interview": {
            "status": iv.get("status", "not_started"),
            "count": len(iv.get("transcript", []) or []),
            "target": INTERVIEW_TURNS,
            "pending_question": iv.get("pending_question"),
            "transcript": iv.get("transcript", []) or [],
            "can_finish": len(iv.get("transcript", []) or []) >= MIN_FINISH_ANSWERS,
        },
        "updated_at": org.get("founder_profile_updated_at"),
    }


# Persist profile onto the org
def _save_profile(org_id: str, profile: dict, mark_done: bool = True):
    upd = {"founder_profile": profile, "founder_profile_updated_at": now_utc()}
    if mark_done:
        upd["founder_interview.status"] = "done"
        upd["founder_interview.pending_question"] = None
    orgs_col.update_one({"id": org_id}, {"$set": upd})


# ---------------------------------------------------------------- models
class AnswerIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


# Payload for manual profile edits
class ProfileIn(BaseModel):
    summary: str = Field(default="", max_length=600)
    personality: str = Field(default="", max_length=600)
    working_style: str = Field(default="", max_length=600)
    communication_style: str = Field(default="", max_length=600)
    decision_style: str = Field(default="", max_length=600)
    risk_appetite: str = Field(default="", max_length=600)
    strengths: str = Field(default="", max_length=600)
    blind_spots: str = Field(default="", max_length=600)
    motivations: str = Field(default="", max_length=600)
    industry_summary: str = Field(default="", max_length=800)


# ---------------------------------------------------------------- endpoints
@router.get("/profile")
def get_profile(user: dict = Depends(current_user)):
    """Owner-only. The founder profile + interview state."""
    org = _require_owner(user)
    return _profile_view(org)


@router.post("/interview/start")
def interview_start(user: dict = Depends(current_user)):
    """Owner-only. Begin (or restart) the deep onboarding conversation. No LLM - opening is fixed."""
    org = _require_owner(user)
    iv = {"status": "in_progress", "transcript": [], "pending_question": OPENING_Q,
          "started_at": now_utc()}
    orgs_col.update_one({"id": org["id"]}, {"$set": {"founder_interview": iv}})
    return {"done": False, "question": OPENING_Q, "count": 0, "target": INTERVIEW_TURNS}


@router.post("/interview/answer")
def interview_answer(body: AnswerIn, user: dict = Depends(current_user)):
    """Owner-only. Record the founder's answer; either return the next connected question (1 LLM call)
    or, once enough is gathered, distill and store the profile (1 LLM call)."""
    org = _require_owner(user)
    iv = org.get("founder_interview") or {}
    if iv.get("status") != "in_progress":
        # auto-start if they answer without starting
        iv = {"status": "in_progress", "transcript": [], "pending_question": OPENING_Q, "started_at": now_utc()}
    transcript = list(iv.get("transcript", []) or [])
    transcript.append({"q": iv.get("pending_question") or OPENING_Q, "a": body.message.strip()})
    count = len(transcript)

    if count >= INTERVIEW_TURNS:
        try:
            profile = _distill(transcript)
        except Exception as e:
            log.error(f"distill failed: {e}")
            raise HTTPException(502, "Could not build your profile right now. Please try again.")
        orgs_col.update_one({"id": org["id"]}, {"$set": {
            "founder_interview.transcript": transcript,
            "founder_interview.status": "done",
            "founder_interview.pending_question": None,
        }})
        _save_profile(org["id"], profile, mark_done=True)
        return {"done": True, "profile": profile, "count": count, "target": INTERVIEW_TURNS}

    try:
        nq = _next_question(transcript)
    except Exception as e:
        log.error(f"next question failed: {e}")
        raise HTTPException(502, "The interview hit a snag. Please try again.")
    orgs_col.update_one({"id": org["id"]}, {"$set": {
        "founder_interview.transcript": transcript,
        "founder_interview.status": "in_progress",
        "founder_interview.pending_question": nq,
    }})
    return {"done": False, "question": nq, "count": count, "target": INTERVIEW_TURNS}


@router.post("/interview/finish")
def interview_finish(user: dict = Depends(current_user)):
    """Owner-only. Distill the profile from whatever has been said so far (>= 2 answers)."""
    org = _require_owner(user)
    iv = org.get("founder_interview") or {}
    transcript = list(iv.get("transcript", []) or [])
    if len(transcript) < MIN_FINISH_ANSWERS:
        raise HTTPException(422, f"Answer at least {MIN_FINISH_ANSWERS} questions before finishing.")
    try:
        profile = _distill(transcript)
    except Exception as e:
        log.error(f"distill (finish) failed: {e}")
        raise HTTPException(502, "Could not build your profile right now. Please try again.")
    _save_profile(org["id"], profile, mark_done=True)
    return {"done": True, "profile": profile, "count": len(transcript), "target": INTERVIEW_TURNS}


@router.put("/profile")
def put_profile(body: ProfileIn, user: dict = Depends(current_user)):
    """Owner-only. Directly set/edit the distilled profile (no LLM). Used for manual tweaks."""
    org = _require_owner(user)
    profile = {k: getattr(body, k).strip() for k in PROFILE_FIELDS}
    if not profile["summary"]:
        raise HTTPException(422, "A short summary is required.")
    _save_profile(org["id"], profile, mark_done=False)
    org = orgs_col.find_one({"id": org["id"]})
    return _profile_view(org)


@router.delete("/profile")
def delete_profile(user: dict = Depends(current_user)):
    """Owner-only. Clear the founder profile (the brain stops tailoring to it)."""
    org = _require_owner(user)
    orgs_col.update_one({"id": org["id"]}, {"$unset": {"founder_profile": "", "founder_interview": ""}})
    return {"cleared": True}
