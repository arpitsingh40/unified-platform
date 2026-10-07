"""Playbook Engine — generic state machine for book frameworks.
Each framework is a Playbook subclass with stages, inputs, prompts, and progress.
Stored in DB per user so it survives restarts and can be resumed anytime."""
import uuid
import json
import logging
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from db import playbooks_col
from security import current_user, now_utc
from ledger import record_ledger, inc_stats

log = logging.getLogger("playbooks")
router = APIRouter(prefix="/api/v1/playbooks")

# Stage status display labels
STAGE_DISPLAY = {
    "not_started": "Not started",
    "in_progress": "In progress",
    "completed": "Completed",
}

# --------------------------------------------------------------------------- Playbook definitions
PLAYBOOKS = {}

# Single playbook stage definition
class Stage:
    def __init__(self, key, label, prompt_template, input_fields=None):
        self.key = key
        self.label = label
        self.prompt_template = prompt_template
        self.input_fields = input_fields or []

# Base playbook state machine class
class Playbook:
    key = ""
    title = ""
    book = ""
    description = ""
    stages = []
    icon = "book"

    # Resolve stage object by key
    @classmethod
    def get_stage(cls, key):
        for s in cls.stages:
            if s.key == key:
                return s
        return cls.stages[0] if cls.stages else None

    # Return the first stage
    @classmethod
    def first_stage(cls):
        return cls.stages[0] if cls.stages else None

    # Return the stage after current key
    @classmethod
    def next_stage(cls, current_key):
        for i, s in enumerate(cls.stages):
            if s.key == current_key and i + 1 < len(cls.stages):
                return cls.stages[i + 1]
        return None

    # Map stage key to progress percentage
    @classmethod
    def progress_pct(cls, stage_key):
        if not cls.stages:
            return 0
        for i, s in enumerate(cls.stages):
            if s.key == stage_key:
                return int(100 * (i) / len(cls.stages))
        return 0

    # Fill stage prompt template with inputs
    @classmethod
    def build_prompt(cls, stage_key, inputs):
        stage = cls.get_stage(stage_key)
        if not stage:
            return ""
        filled = {}
        for f in stage.input_fields:
            filled[f] = inputs.get(f, "")
        return stage.prompt_template.format(**filled)

    # Serialize playbook metadata for API
    @classmethod
    def registry(cls):
        return {"key": cls.key, "title": cls.title, "book": cls.book,
                "description": cls.description, "icon": cls.icon,
                "stages": [{"key": s.key, "label": s.label, "input_fields": s.input_fields} for s in cls.stages]}

# ----------------------------------------------------------------------- Hedgehog Concept
class HedgehogPlaybook(Playbook):
    key = "hedgehog"
    title = "Hedgehog Concept"
    book = "Good to Great"
    description = "Find the intersection of what you're deep-passionate about, what you can be best in the world at, and what drives your economic engine."
    icon = "target"
    stages = [
        Stage("passion", "What you're passionate about",
              "You deeply care about: {passion_input}",
              ["passion_input"]),
        Stage("best", "What you can be best at",
              "You can be the best in the world at: {best_input}",
              ["best_input"]),
        Stage("engine", "What drives your economic engine",
              "Your economic engine: {engine_input} — What metrics drive your flywheel?",
              ["engine_input"]),
        Stage("intersection", "Your Hedgehog Concept",
              "Hedgehog: passionate about {passion_input}, best at {best_input}, driven by {engine_input}.",
              ["passion_input", "best_input", "engine_input"]),
    ]

PLAYBOOKS["hedgehog"] = HedgehogPlaybook

# ----------------------------------------------------------------------- Five Forces
class FiveForcesPlaybook(Playbook):
    key = "five_forces"
    title = "Five Forces"
    book = "Competitive Strategy"
    description = "Analyze industry competition across five forces to find strategic positioning."
    icon = "radar"
    stages = [
        Stage("rivalry", "Industry Rivalry",
              "Existing competitors in your space: {rivalry_input}",
              ["rivalry_input"]),
        Stage("entrants", "Threat of New Entrants",
              "Barriers to entry in your market: {entrants_input}",
              ["entrants_input"]),
        Stage("substitutes", "Threat of Substitutes",
              "Substitute products/services: {substitutes_input}",
              ["substitutes_input"]),
        Stage("suppliers", "Supplier Power",
              "Your key suppliers and their bargaining power: {suppliers_input}",
              ["suppliers_input"]),
        Stage("buyers", "Buyer Power",
              "Your customers' bargaining power: {buyers_input}",
              ["buyers_input"]),
        Stage("positioning", "Strategic Position",
              "Based on rivalry={rivalry_input}, entrants={entrants_input}, substitutes={substitutes_input}, "
              "suppliers={suppliers_input}, buyers={buyers_input} — your strategic position and moat.",
              ["rivalry_input", "entrants_input", "substitutes_input", "suppliers_input", "buyers_input"]),
    ]

PLAYBOOKS["five_forces"] = FiveForcesPlaybook

# ----------------------------------------------------------------------- Hook Model
class HookModelPlaybook(Playbook):
    key = "hook_model"
    title = "Hook Model"
    book = "Hooked"
    description = "Build habit-forming products through a four-step loop: Trigger → Action → Variable Reward → Investment."
    icon = "activity"
    stages = [
        Stage("trigger", "Trigger",
              "What external or internal trigger prompts user action? Current triggers: {trigger_input}",
              ["trigger_input"]),
        Stage("action", "Action",
              "What is the simplest action the user takes in response? Current friction: {action_input}",
              ["action_input"]),
        Stage("reward", "Variable Reward",
              "What variable reward keeps users returning? Current reward: {reward_input}",
              ["reward_input"]),
        Stage("investment", "Investment",
              "What investment (effort, data, reputation) makes users value the service more over time? Current investment: {investment_input}",
              ["investment_input"]),
        Stage("audit", "Hook Audit",
              "FULL HOOK AUDIT: Trigger={trigger_input}, Action={action_input}, Reward={reward_input}, "
              "Investment={investment_input}. Where is the loop leak?",
              ["trigger_input", "action_input", "reward_input", "investment_input"]),
    ]

PLAYBOOKS["hook_model"] = HookModelPlaybook

# ----------------------------------------------------------------------- GTD Workflow
class GTDPlaybook(Playbook):
    key = "gtd"
    title = "GTD Workflow"
    book = "Getting Things Done"
    description = "Capture → Clarify → Organize → Reflect → Engage — clear your mind and get things done."
    icon = "list_checks"
    stages = [
        Stage("capture", "Capture",
              "What is cluttering your mind right now? Dump it all: {capture_input}",
              ["capture_input"]),
        Stage("clarify", "Clarify",
              "For each item: What is it? Is it actionable? If yes, what is the next physical action? Clarify: {clarify_input}",
              ["clarify_input"]),
        Stage("organize", "Organize",
              "Organize into categories (next actions, projects, waiting, someday/maybe, reference). Organize: {organize_input}",
              ["organize_input"]),
        Stage("reflect", "Reflect",
              "Weekly review: what has changed, what needs updating, what can be dropped? Reflect: {reflect_input}",
              ["reflect_input"]),
        Stage("engage", "Engage",
              "Based on capture={capture_input}, clarify={clarify_input}, organize={organize_input}, "
              "reflect={reflect_input} — what do you DO right now?",
              ["capture_input", "clarify_input", "organize_input", "reflect_input"]),
    ]

PLAYBOOKS["gtd"] = GTDPlaybook

# ----------------------------------------------------------------------- Essentialist 90% Rule
class EssentialismPlaybook(Playbook):
    key = "essentialism"
    title = "Essentialist 90% Rule"
    book = "Essentialism"
    description = "If it's not a clear yes, it's a no. Apply the 90% rule to every opportunity."
    icon = "scale"
    stages = [
        Stage("opportunities", "List Opportunities",
              "What opportunities/options are you considering? {opportunities_input}",
              ["opportunities_input"]),
        Stage("evaluate", "90% Rule Evaluation",
              "For each option, is it a HELL YES (≥90/100)? Evaluate: {evaluate_input}",
              ["evaluate_input"]),
        Stage("tradeoff", "Trade-off Decision",
              "What are you saying no to by saying yes to each? Trade-offs: {tradeoff_input}",
              ["tradeoff_input"]),
        Stage("commit", "Your Essential Yes",
              "Your essential yes: committed to {commit_input} — and saying no to everything else.",
              ["commit_input"]),
    ]

PLAYBOOKS["essentialism"] = EssentialismPlaybook

# ----------------------------------------------------------------------- Habit Loop (Atomic Habits + Power of Habit)
class HabitLoopPlaybook(Playbook):
    key = "habit_loop"
    title = "Habit Loop"
    book = "Atomic Habits / The Power of Habit"
    description = "Identify the cue → craving → response → reward loop and redesign your habits."
    icon = "activity"
    stages = [
        Stage("cue", "Cue",
              "What triggers the habit? Current cue: {cue_input}",
              ["cue_input"]),
        Stage("craving", "Craving",
              "What craving drives the behavior? Current craving: {craving_input}",
              ["craving_input"]),
        Stage("response", "Response",
              "What behavior does the cue+craving produce? Current response: {response_input}",
              ["response_input"]),
        Stage("reward", "Reward",
              "What reward satisfies the craving? Current reward: {reward_input}",
              ["reward_input"]),
        Stage("redesign", "Habit Redesign",
              "REDESIGN: Keep Cue={cue_input}, change Craving={craving_input}, Response={response_input}, Reward={reward_input}. "
              "How do you make it obvious, attractive, easy, and satisfying?",
              ["cue_input", "craving_input", "response_input", "reward_input"]),
    ]

PLAYBOOKS["habit_loop"] = HabitLoopPlaybook

# ----------------------------------------------------------------------- OKR Builder
class OKRPlaybook(Playbook):
    key = "okr_builder"
    title = "OKR Builder"
    book = "Measure What Matters"
    description = "Set Objectives and Key Results that cascade from founder vision to team execution."
    icon = "target"
    stages = [
        Stage("objective", "Objective",
              "What is the single most important thing to achieve this quarter? Objective: {objective_input}",
              ["objective_input"]),
        Stage("key_results", "Key Results",
              "3-5 measurable key results that show you achieved the objective. Key Results: {kr_input}",
              ["kr_input"]),
        Stage("cascade", "Cascade",
              "How does this objective cascade to teams/individuals? Cascade: {cascade_input}",
              ["cascade_input"]),
        Stage("commit", "Commit & Publish",
              "Final OKR: Objective={objective_input}, KRs={kr_input}, Cascade={cascade_input}.",
              ["objective_input", "kr_input", "cascade_input"]),
    ]

PLAYBOOKS["okr_builder"] = OKRPlaybook

# ----------------------------------------------------------------------- Circle of Influence
class CircleInfluencePlaybook(Playbook):
    key = "circle_influence"
    title = "Circle of Influence"
    book = "The 7 Habits of Highly Effective People"
    description = "Focus energy on what you can control, not what you can't."
    icon = "circle_dot"
    stages = [
        Stage("concerns", "Circle of Concern",
              "What worries/concerns are on your mind? All of them: {concerns_input}",
              ["concerns_input"]),
        Stage("influence", "Circle of Influence",
              "Which of these concerns can you actually influence? Your circle: {influence_input}",
              ["influence_input"]),
        Stage("control", "Circle of Control",
              "Which can you directly control? Circle of control: {control_input}",
              ["control_input"]),
        Stage("refocus", "Proactive Refocus",
              "REFOCUS: Stop worrying about concerns outside your control. "
              "Put energy into: {control_input} (control) and {influence_input} (influence). "
              "Let go of the rest.",
              ["control_input", "influence_input"]),
    ]

PLAYBOOKS["circle_influence"] = CircleInfluencePlaybook

# ----------------------------------------------------------------------- Flywheel
class FlywheelPlaybook(Playbook):
    key = "flywheel"
    title = "Flywheel"
    book = "Good to Great"
    description = "Identify and accelerate your growth flywheel — the virtuous cycle that compounds over time."
    icon = "activity"
    stages = [
        Stage("inputs", "Flywheel Inputs",
              "What inputs/steps start the cycle? Current inputs: {inputs_input}",
              ["inputs_input"]),
        Stage("loop", "The Loop",
              "How does each step feed the next? Map the loop: {loop_input}",
              ["loop_input"]),
        Stage("acceleration", "Acceleration Levers",
              "Which step, if improved, accelerates the entire flywheel most? Levers: {acceleration_input}",
              ["acceleration_input"]),
        Stage("complete", "Flywheel Visualization",
              "FLYWHEEL: {inputs_input} → {loop_input}. Key lever: {acceleration_input}. "
              "Turn it one more degree every day.",
              ["inputs_input", "loop_input", "acceleration_input"]),
    ]

PLAYBOOKS["flywheel"] = FlywheelPlaybook

# ----------------------------------------------------------------------- Biography Bank (simple injector)
BIOGRAPHY_LENSES = {}  # populated at import

# Load founder biography files into memory
def _load_biographies():
    import os
    from pathlib import Path
    knowledge_dir = Path(__file__).parent / "knowledge"
    bio_files = [
        "steve_jobs.md", "elon_musk.md", "jeff_bezos.md",
        "sheryl_sandberg.md", "warren_buffett.md",
        "paul_graham.md", "sam_altman.md",
    ]
    for fname in bio_files:
        fpath = knowledge_dir / fname
        if fpath.exists():
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
                BIOGRAPHY_LENSES[fname.replace(".md", "")] = text[:2000]
            except Exception:
                pass

_load_biographies()

# Build founder-story context block if relevant
def biography_block(industry=None, context=""):
    if not BIOGRAPHY_LENSES:
        return ""
    blocks = []
    context_lower = (context or "").lower()
    for slug, text in BIOGRAPHY_LENSES.items():
        relevance = sum(1 for w in context_lower.split() if w in text[:500].lower())
        if relevance >= 1:
            blocks.append(f"[{slug.replace('_',' ').title()}]: {text[:600]}")
    if not blocks:
        return ""
    return "FOUNDER STORIES (real context from biography archives — inject genuine cases):\n" + "\n\n".join(blocks[:3])

# --------------------------------------------------------------------------- CRUD endpoints
# Request schema for creating a playbook
class PlaybookCreateIn(BaseModel):
    playbook_key: str = Field(min_length=1, max_length=50)

# Request schema for updating a playbook
class PlaybookUpdateIn(BaseModel):
    stage_key: Optional[str] = None
    inputs: dict = {}
    status: Optional[str] = None

# List user's playbooks and available frameworks
@router.get("")
def list_playbooks(user: dict = Depends(current_user)):
    items = list(playbooks_col.find({"user_id": user["id"]}).sort("updated_at", -1))
    return {"playbooks": [serialize(p) for p in items],
            "available": [k for k in PLAYBOOKS]}

# List all available playbook frameworks
@router.get("/available")
def available_playbooks():
    return {"playbooks": [cls.registry() for cls in PLAYBOOKS.values()]}

# Create or resume a playbook instance
@router.post("")
def create_playbook(body: PlaybookCreateIn, user: dict = Depends(current_user)):
    cls = PLAYBOOKS.get(body.playbook_key)
    if not cls:
        raise HTTPException(404, f"Unknown playbook: {body.playbook_key}")
    existing = playbooks_col.find_one({"user_id": user["id"], "playbook_key": body.playbook_key, "status": {"$ne": "completed"}})
    if existing:
        return serialize(existing)
    doc = {
        "id": str(uuid.uuid4()), "user_id": user["id"],
        "playbook_key": body.playbook_key,
        "title": cls.title, "book": cls.book,
        "current_stage": cls.first_stage().key if cls.first_stage() else "",
        "inputs": {},
        "status": "in_progress",
        "created_at": now_utc(), "updated_at": now_utc(),
    }
    playbooks_col.insert_one(doc)
    inc_stats({"playbooks_created": 1})
    return serialize(doc)

# Fetch a playbook with current stage detail
@router.get("/{playbook_id}")
def get_playbook(playbook_id: str, user: dict = Depends(current_user)):
    p = playbooks_col.find_one({"id": playbook_id, "user_id": user["id"]})
    if not p:
        raise HTTPException(404, "Playbook not found")
    return serialize_with_stage(p)

# Update playbook stage, inputs, or status
@router.patch("/{playbook_id}")
def update_playbook(playbook_id: str, body: PlaybookUpdateIn, user: dict = Depends(current_user)):
    p = playbooks_col.find_one({"id": playbook_id, "user_id": user["id"]})
    if not p:
        raise HTTPException(404, "Playbook not found")
    cls = PLAYBOOKS.get(p["playbook_key"])
    if not cls:
        raise HTTPException(400, "Playbook definition not found")
    updates = {"updated_at": now_utc()}
    if body.inputs:
        merged = {**p.get("inputs", {}), **body.inputs}
        updates["inputs"] = merged
    if body.status:
        updates["status"] = body.status
    if body.stage_key:
        # validate stage exists
        if not cls.get_stage(body.stage_key):
            raise HTTPException(400, f"Unknown stage: {body.stage_key}")
        updates["current_stage"] = body.stage_key
    playbooks_col.update_one({"id": playbook_id}, {"$set": updates})
    fresh = playbooks_col.find_one({"id": playbook_id})
    return serialize_with_stage(fresh)

# Advance playbook to the next stage
@router.post("/{playbook_id}/advance")
def advance_playbook(playbook_id: str, user: dict = Depends(current_user)):
    p = playbooks_col.find_one({"id": playbook_id, "user_id": user["id"]})
    if not p:
        raise HTTPException(404, "Playbook not found")
    cls = PLAYBOOKS.get(p["playbook_key"])
    if not cls:
        raise HTTPException(400, "Playbook definition not found")
    next_s = cls.next_stage(p.get("current_stage", ""))
    if not next_s:
        playbooks_col.update_one({"id": playbook_id}, {"$set": {"status": "completed", "updated_at": now_utc()}})
        inc_stats({"playbooks_completed": 1})
        fresh = playbooks_col.find_one({"id": playbook_id})
        return serialize_with_stage(fresh)
    playbooks_col.update_one({"id": playbook_id}, {"$set": {"current_stage": next_s.key, "updated_at": now_utc()}})
    fresh = playbooks_col.find_one({"id": playbook_id})
    return serialize_with_stage(fresh)

# --------------------------------------------------------------------------- serialization
# Strip Mongo metadata and ISO-format dates
def serialize(p):
    if isinstance(p, dict):
        return {k: v.isoformat() if isinstance(v, datetime) else v for k, v in p.items() if k != "_id"}
    return p

# Serialize playbook with stage info and prompt
def serialize_with_stage(p):
    cls = PLAYBOOKS.get(p["playbook_key"])
    out = serialize(p)
    out["progress_pct"] = cls.progress_pct(p.get("current_stage", "")) if cls else 0
    out["stage_info"] = cls.get_stage(p.get("current_stage", "")).__dict__ if cls and cls.get_stage(p.get("current_stage", "")) else {}
    out["registry"] = cls.registry() if cls else {}
    out["prompt"] = cls.build_prompt(p.get("current_stage", ""), p.get("inputs", {})) if cls else ""
    return out
