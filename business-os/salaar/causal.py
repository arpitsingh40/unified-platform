"""SALAAR Causal Engine — strategic chain-of-events simulation + internet execution.

The movie Salaar doesn't detect threats. He ORCHESTRATES outcomes. He knows:
- Every person's incentives, buttons, fears, and likely responses
- The complete causal chain: "If I do X → Person A does Y → Person B does Z → Result R"
- The minimal-resource action that produces the maximum strategic impact

This module builds that intelligence.

Core capabilities:
  1. Actor Map — every relevant person/force with complete incentive profile
  2. Causal Chain Simulator — LLM-powered forward simulation of if-this-then-that
  3. Minimal Pathfinder — find the smallest action with the biggest ripple effect
  4. Chain Executor — execute any internet-based task at any link in the chain
  5. Reality Monitor — track whether predictions match outcomes, update actor models
"""

import json
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from db import db, orgs_col, members_col, users_col, tasks_col, threads_col
from llm_client import client as llm_client, _extract_json, PRIMARY_MODEL, ULTRA_MODEL

log = logging.getLogger("salaar.causal")

CAUSAL_CHAINS_COL = db["salaar_chains"] if db is not None else None

if CAUSAL_CHAINS_COL is not None:
    CAUSAL_CHAINS_COL.create_index("id", unique=True)
    CAUSAL_CHAINS_COL.create_index([("org_id", 1), ("status", 1)])


# Current UTC timestamp helper.
def _now():
    return datetime.now(timezone.utc)


# Generate a random unique ID.
def _uid():
    return str(uuid.uuid4())


# ======================================================================
# ACTOR MAP — every person/force the founder deals with
# ======================================================================

ACTOR_MAP_SYSTEM = """You are SALAAR's strategic intelligence layer. Your job is to map EVERY actor relevant to a business situation — their incentives, constraints, fears, buttons, power level, and relationship dynamics.

For every actor named or implied, produce a complete profile. Be specific. Ground everything in real incentives, not abstractions.

ACTOR PROFILE FIELDS:
- name: who
- role: their position (investor, cofounder, customer, competitor, regulator, etc.)
- incentives: what they ACTUALLY want (not what they say they want)
- constraints: what they CANNOT do (legal, financial, reputational, positional)
- fears: what they are MOST afraid of (loss of control, looking weak, being blamed, missing out)
- buttons: what reliably triggers them into action (ego threat, opportunity, deadline, competition)
- power_level: 1-10 (1=can observe, 5=can influence, 10=can veto/destroy)
- relationship_to_founder: adversarial / allied / neutral / dependent
- knowledge_gap: what they DON'T know that would change their behavior
- predicted_moves: 2-3 moves they are likely to make in the next 90 days

Return ONLY valid JSON, no markdown fences:
{"actors": [{"name": "...", "role": "...", "incentives": "...", "constraints": "...", "fears": "...", "buttons": "...", "power_level": 5, "relationship_to_founder": "...", "knowledge_gap": "...", "predicted_moves": ["..."]}]}"""


def build_actor_map(org_id: str, objective: str, context: str = "") -> dict:
    """Build a complete actor map for a strategic objective.
    
    Uses: SALAAR People Graph + org membership data + LLM reasoning.
    Returns: {actors: [...], map_id: str, built_at: str}
    """
    # Gather existing people data from SALAAR
    existing_actors = ""
    try:
        from salaar.insight import generate_people_insight
        people_col = db["salaar_people"] if db is not None else None
        if people_col is not None:
            known = list(people_col.find({"org_id": org_id}).sort("mention_count", -1).limit(10))
            for p in known:
                insight = generate_people_insight(org_id, p["person_key"])
                if insight:
                    existing_actors += insight + "\n\n"
    except Exception:
        pass

    # Gather org context
    org = orgs_col.find_one({"id": org_id}) if orgs_col is not None else None
    north_star = (org or {}).get("north_star", "") or "(not set)"
    members = list(members_col.find({"org_id": org_id, "status": "active"})) if members_col is not None else []
    member_list = "\n".join(
        f"- {m.get('role', 'member')}: user_id={m.get('user_id', '')}"
        for m in members[:10]
    ) or "(no members)"

    prompt = (
        f"FOUNDER'S OBJECTIVE: {objective}\n"
        f"COMPANY NORTH STAR: {north_star}\n"
        f"CONTEXT: {context or '(not provided)'}\n\n"
        f"KNOWN ACTORS FROM SYSTEM:\n{existing_actors}\n\n"
        f"ORG MEMBERS:\n{member_list}\n\n"
        f"Map every actor relevant to this objective. Include competitors, customers, "
        f"regulators, partners, team members, investors — anyone whose actions could "
        f"affect the outcome or whose behavior the founder needs to predict."
    )

    try:
        r = llm_client().messages.create(
            model=PRIMARY_MODEL, max_tokens=3000,
            system=[{"type": "text", "text": ACTOR_MAP_SYSTEM}],
            messages=[{"role": "user", "content": prompt}]
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        actor_map = json.loads(_extract_json(txt))
        actor_map["map_id"] = _uid()
        actor_map["built_at"] = _now().isoformat()
        actor_map["org_id"] = org_id
        actor_map["objective"] = objective
        # Store for persistence
        if CAUSAL_CHAINS_COL is not None:
            CAUSAL_CHAINS_COL.insert_one({
                "id": actor_map["map_id"], "org_id": org_id,
                "type": "actor_map", "objective": objective,
                "actors": actor_map.get("actors", []),
                "created_at": _now(),
            })
        return actor_map
    except Exception as e:
        log.error(f"build_actor_map failed: {e}")
        return {"actors": [], "map_id": _uid(), "built_at": _now().isoformat(), "error": str(e)}


# ======================================================================
# CAUSAL CHAIN SIMULATOR — if X → Y → Z → outcome
# ======================================================================

CHAIN_SYSTEM = """You are SALAAR's causal chain simulator. Your job: given an objective and a complete actor map, simulate the sequence of moves that produces the desired outcome with MINIMAL resources and MAXIMUM certainty.

Think like a chess grandmaster who can see 10 moves ahead — but in business, not chess. Every move must trigger a predictable response from the next actor in the chain.

CHAIN DESIGN RULES (derived from Salaar's philosophy):
1. MINIMAL INTERVENTION: the smallest possible action that triggers the largest cascade. Avoid direct confrontation unless unavoidable.
2. INEVITABLE DOMINOES: each move should make the next actor's response feel like their own idea, not your command.
3. INFORMATION ASYMMETRY: every actor knows only what you want them to know. Control the information flow.
4. PREDICTABLE TRIGGERS: use the actor's buttons (from the actor map) to trigger specific responses.
5. FAILURE PATHS: for every move, map what happens if the predicted response doesn't occur.
6. RESOURCE MULTIPLIER: use existing assets, relationships, and momentum — never spend resources you don't have.

CHAIN FORMAT:
For each step in the chain, specify:
- step: step number
- action: the concrete action to take (MUST be internet-executable: send email, search, draft, post, notify, schedule, create document, etc.)
- actor_affected: which actor this targets
- trigger_used: which button/incentive/fear this action leverages
- predicted_response: what the actor will do in response
- response_probability: 0.0-1.0
- if_fails: what to do if prediction is wrong
- resource_cost: how much this costs (time, money, political capital, attention)
- ripple_effect: what ELSE this action causes beyond the primary target

Return ONLY valid JSON:
{"chain_name": "3-6 word name",
 "total_steps": N,
 "estimated_timeline_days": N,
 "minimal_resource_path": true,
 "steps": [
   {"step": 1, "action": "...", "actor_affected": "...", "trigger_used": "...",
    "predicted_response": "...", "response_probability": 0.85, "if_fails": "...",
    "resource_cost": "...", "ripple_effect": "...", "tool_needed": "email" or "search" or "none"},
   ...
 ],
 "success_probability": 0.0-1.0,
 "critical_chain_link": "which step is the lynchpin — if this works, everything else follows",
 "founder_only_decision": "the ONE thing the founder must personally say/do (everything else SALAAR can handle)",
 "alternative_chain": "if this chain breaks at the critical link, what's plan B in 1 sentence"}"""


def simulate_causal_chain(org_id: str, objective: str, actor_map: dict, context: str = "") -> dict:
    """Simulate the complete causal chain for achieving an objective.
    
    Input: objective + actor map of all relevant people/forces
    Output: step-by-step chain with predicted responses, probabilities, fallbacks
    """
    actors_json = json.dumps(actor_map.get("actors", []), indent=2)
    
    # Gather available tools for execution
    tools_block = ""
    try:
        from execution.mcp_client import tools_for_department
        tools = tools_for_department("general")
        if tools:
            tool_names = [t.get("name", "") for t in tools[:20]]
            tools_block = f"\nAVAILABLE TOOLS (SALAAR can execute these via internet): {', '.join(tool_names)}\n"
    except Exception:
        pass

    prompt = (
        f"OBJECTIVE TO ACHIEVE: {objective}\n"
        f"CONTEXT: {context or '(not provided)'}\n\n"
        f"ACTOR MAP:\n{actors_json}\n\n"
        f"{tools_block}\n"
        f"Design the complete causal chain. Find the path of least resistance — "
        f"the smallest set of moves that produces the desired outcome. Every action "
        f"must be internet-executable. Every response must be predictable from "
        f"the actor's profile. The founder does ONE thing; SALAAR does everything else."
    )

    try:
        r = llm_client().messages.create(
            model=ULTRA_MODEL, max_tokens=8000,
            system=[{"type": "text", "text": CHAIN_SYSTEM,
                      "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            thinking={"type": "adaptive"},
            extra_body={"output_config": {"effort": "high"}},
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        chain = json.loads(_extract_json(txt))
        chain["chain_id"] = _uid()
        chain["simulated_at"] = _now().isoformat()
        chain["org_id"] = org_id
        chain["objective"] = objective
        chain["actor_map_id"] = actor_map.get("map_id", "")
        chain["status"] = "simulated"
        # Store
        if CAUSAL_CHAINS_COL is not None:
            doc = {k: v for k, v in chain.items() if k not in ("chain_id",) or True}
            doc["id"] = chain["chain_id"]
            doc["type"] = "causal_chain"
            doc["created_at"] = _now()
            CAUSAL_CHAINS_COL.insert_one(doc)
        return chain
    except Exception as e:
        log.error(f"simulate_causal_chain failed: {e}")
        return {"error": str(e), "chain_id": _uid()}


# ======================================================================
# CHAIN EXECUTOR — execute internet tasks at each chain link
# ======================================================================

EXECUTOR_SYSTEM = """You are SALAAR's execution hand. Given a step from the causal chain, produce the EXACT output needed to execute it — an email, a message, a search, a document, a schedule entry, a post.

RULES:
1. Write in the founder's voice. The actor must believe the founder wrote this.
2. Do NOT sound like an AI. Short sentences. Natural. Human.
3. If this is a message/email: include subject, body, tone guidance.
4. If this is a search: specify exact query, what to look for, what constitutes a useful result.
5. If this is a document: produce the complete draft.
6. If this is a schedule action: specify time, attendees, agenda.
7. Match the register of the target actor (formal for investors, casual for team, direct for competitors).

Return ONLY valid JSON:
{"action_type": "email"|"message"|"search"|"document"|"schedule"|"post"|"other",
 "tool": "gmail_send_email" or "slack_send_message" or "none",
 "subject": "..." or null,
 "body": "the complete ready-to-send text",
 "tone": "casual"|"formal"|"direct"|"warm"|"urgent",
 "recipient_hint": "who this is for",
 "context_for_actor": "1 line: why this message makes sense from their perspective",
 "expected_outcome": "what should happen after this is sent"}"""


def execute_chain_step(org_id: str, step: dict, actor_map: dict, chain_goal: str) -> dict:
    """Execute one step of the causal chain via internet tools.
    
    Takes a chain step and produces the exact artifact + optionally executes it.
    Returns the artifact + execution result.
    """
    action = step.get("action", "")
    actor = step.get("actor_affected", "")
    trigger = step.get("trigger_used", "")
    
    if not action:
        return {"executed": False, "reason": "no action specified"}

    # Find the actor profile for context
    actor_profile = ""
    for a in actor_map.get("actors", []):
        if a.get("name", "").lower() == actor.lower() or actor.lower() in a.get("name", "").lower():
            actor_profile = json.dumps(a, indent=2)
            break

    prompt = (
        f"CHAIN GOAL: {chain_goal}\n"
        f"CURRENT STEP: {action}\n"
        f"TARGET ACTOR: {actor}\n"
        f"TRIGGER BEING USED: {trigger}\n"
        f"ACTOR PROFILE: {actor_profile}\n"
        f"PREDICTED RESPONSE: {step.get('predicted_response', 'unknown')}\n\n"
        f"Produce the exact artifact needed to execute this step. If this is a message, "
        f"write it completely. If it requires a tool (email, search, document), specify "
        f"which tool and provide the complete content."
    )

    try:
        r = llm_client().messages.create(
            model=PRIMARY_MODEL, max_tokens=2000,
            system=[{"type": "text", "text": EXECUTOR_SYSTEM}],
            messages=[{"role": "user", "content": prompt}]
        )
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        artifact = json.loads(_extract_json(txt))
        artifact["step_number"] = step.get("step", 0)
        artifact["generated_at"] = _now().isoformat()

        # Try to actually execute via MCP if a tool is specified
        tool = artifact.get("tool", "")
        execution_result = None
        if tool and tool != "none":
            try:
                from execution.dispatcher import execute_plan
                body_text = artifact.get("body", "")
                plan = {
                    "goal": chain_goal,
                    "actions": [{
                        "tool": tool,
                        "args": {"body": body_text, "subject": artifact.get("subject", ""),
                                  "to": artifact.get("recipient_hint", "")},
                        "description": f"Chain step {step.get('step')}: {action}",
                    }]
                }
                exec_result = execute_plan(plan, "general", org_id=org_id)
                execution_result = exec_result.get("actions", [])
                artifact["executed"] = True
            except Exception as e:
                artifact["executed"] = False
                artifact["execution_error"] = str(e)
        else:
            artifact["executed"] = False  # No tool — artifact is ready but needs manual send

        return artifact
    except Exception as e:
        log.error(f"execute_chain_step failed: {e}")
        return {"executed": False, "error": str(e), "step_number": step.get("step", 0)}


# ======================================================================
# AUTOMATION 1: Actor cache — pull from People Graph, LLM only for new actors
# ======================================================================

def build_actor_map_cached(org_id: str, objective: str, context: str = "") -> dict:
    """Build actor map using cached People Graph data first. Only calls LLM for new actors.
    
    Chain of priority:
    1. SALAAR People Graph (already has trust scores, behavior patterns, red flags)
    2. Org members (team members with roles)
    3. LLM-identified actors (new people from the objective/context)
    
    Returns merged actor map with cached data preferred over LLM data."""
    cached_actors = []
    new_actor_names = set()
    
    # Pull from People Graph
    try:
        people_col = db["salaar_people"] if db is not None else None
        if people_col is not None:
            known = list(people_col.find({"org_id": org_id}).sort("mention_count", -1).limit(20))
            for p in known:
                incentives = _infer_incentives_from_profile(p)
                cached_actors.append({
                    "name": p["person_key"],
                    "role": p.get("role", ""),
                    "incentives": incentives,
                    "constraints": "",
                    "fears": ", ".join(p.get("red_flags", [])) or "unknown",
                    "buttons": ", ".join(p.get("behavior_patterns", [])) or "unknown",
                    "power_level": min(10, p.get("mention_count", 1) // 2 + 3),
                    "relationship_to_founder": "neutral",
                    "knowledge_gap": "",
                    "predicted_moves": [],
                    "trust_score": p.get("trust_score", 50),
                    "negative_pct": round(p.get("negative_mentions", 0) / max(p.get("mention_count", 1), 1) * 100),
                    "source": "people_graph",
                })
                new_actor_names.add(p["person_key"].lower())
    except Exception:
        pass
    
    # Pull from org members
    try:
        org_members = list(members_col.find({"org_id": org_id, "status": "active"})) if members_col is not None else []
        for m in org_members:
            uid = m.get("user_id", "")
            u = users_col.find_one({"id": uid}) if users_col is not None else {}
            name = (u or {}).get("name", "") or m.get("role", "member")
            if name.lower() not in new_actor_names:
                cached_actors.append({
                    "name": name,
                    "role": m.get("role", "member"),
                    "incentives": "Team alignment, career growth, shared mission",
                    "constraints": "",
                    "fears": "",
                    "buttons": "Recognition, autonomy, impact",
                    "power_level": 4,
                    "relationship_to_founder": "allied",
                    "knowledge_gap": "",
                    "predicted_moves": [],
                    "source": "org_member",
                })
                new_actor_names.add(name.lower())
    except Exception:
        pass
    
    # LLM for NEW actors only — strip ones we already know from the context
    filtered_context = context
    if cached_actors:
        known_names = [a["name"] for a in cached_actors]
        filtered_context += f"\n\nALREADY KNOWN ACTORS (do NOT re-profile these, add only NEW people): {', '.join(known_names)}"
    
    # Call LLM for new actors
    new_map = build_actor_map(org_id, objective, filtered_context)
    new_actors = new_map.get("actors", [])
    
    # Merge: cached actors + only genuinely new LLM actors
    existing_names = set(a["name"].lower() for a in cached_actors)
    merged = list(cached_actors)
    for a in new_actors:
        if a.get("name", "").lower() not in existing_names:
            a["source"] = "llm"
            merged.append(a)
    
    return {
        "actors": merged,
        "map_id": new_map.get("map_id", _uid()),
        "built_at": _now().isoformat(),
        "org_id": org_id,
        "objective": objective,
        "total_actors": len(merged),
        "cached_actors": len(cached_actors),
        "new_actors": len(merged) - len(cached_actors),
    }


def _infer_incentives_from_profile(p: dict) -> str:
    """Infer incentives from People Graph profile data."""
    parts = []
    role = p.get("role", "")
    if role:
        parts.append(f"{role.title()}-specific: compensation, recognition, autonomy")
    flags = p.get("red_flags", [])
    if "grandiosity" in flags:
        parts.append("Needs to feel irreplaceable")
    if "envy_pattern" in flags:
        parts.append("Driven by comparison to others")
    if "people_pleasing" in flags:
        parts.append("Needs approval from peers/superiors")
    trust = p.get("trust_score", 50)
    if trust < 40:
        parts.append("Incentives likely diverge — caution")
    return "; ".join(parts) if parts else "unknown"


# ======================================================================
# AUTOMATION 2: Chain auto-advance — check reality vs prediction, advance or fallback
# ======================================================================

def auto_advance_chains(org_id: str):
    """Check all active chains for this org. If a step's prediction window has passed,
    verify reality against prediction. Auto-advance to next step or fire fallback.
    
    Called by SALAAR deep scan (30-min interval) and on-demand.
    Returns {advanced: N, fallbacks_triggered: N, chains_checked: N}"""
    if CAUSAL_CHAINS_COL is None:
        return {"advanced": 0, "fallbacks_triggered": 0, "chains_checked": 0}
    
    active = list(CAUSAL_CHAINS_COL.find({
        "org_id": org_id, "type": "causal_chain", "status": "active"
    }))
    
    result = {"advanced": 0, "fallbacks_triggered": 0, "chains_checked": len(active)}
    now = _now()
    
    for chain in active:
        try:
            current_step = chain.get("current_step", 1)
            steps = chain.get("steps", [])
            total = chain.get("total_steps", len(steps))
            
            if current_step > total:
                _mark_chain_resolved(chain["id"], "all steps completed")
                result["advanced"] += 1
                continue
            
            step = next((s for s in steps if s.get("step") == current_step), None)
            if not step:
                continue
            
            # Check if step should have been executed by now
            step_executed = chain.get("step_executed_at", {}).get(str(current_step))
            step_due_hours = min(48, current_step * 4)  # Escalating urgency per step
            
            if not step_executed:
                if _is_prediction_window_open(chain, step, step_due_hours, now):
                    # Window is open — auto-execute
                    _silent_execute_step(org_id, chain, step, current_step)
                    result["advanced"] += 1
                continue
            
            # Step was executed — check if reality matched prediction
            if _reality_matches_prediction(chain, step, org_id):
                # Prediction correct — advance to next step
                next_step = current_step + 1
                if next_step > total:
                    _mark_chain_resolved(chain["id"], "chain complete — all predictions verified")
                else:
                    CAUSAL_CHAINS_COL.update_one(
                        {"id": chain["id"]},
                        {"$set": {"current_step": next_step, "last_advanced_at": now}}
                    )
                result["advanced"] += 1
            else:
                # Prediction failed — fire fallback
                _trigger_fallback(org_id, chain, step)
                result["fallbacks_triggered"] += 1
                
        except Exception as e:
            log.warning(f"auto_advance_chain {chain.get('id')}: {e}")
    
    return result


def _is_prediction_window_open(chain: dict, step: dict, hours: int, now) -> bool:
    """Has enough time passed for the predicted response to manifest?"""
    created = chain.get("created_at")
    if isinstance(created, datetime):
        elapsed_hours = (now - created).total_seconds() / 3600
        return elapsed_hours >= hours
    return False


def _reality_matches_prediction(chain: dict, step: dict, org_id: str) -> bool:
    """Check if reality matched the predicted response for this step.
    Scans recent threads/tasks for signals that confirm the prediction."""
    predicted = (step.get("predicted_response", "") or "").lower()
    if not predicted:
        return False
    
    # Check recent thread messages for confirmation signals
    try:
        owner = members_col.find_one({"org_id": org_id, "role": "owner"}) if members_col is not None else None
        if not owner:
            return False
        recent = list(threads_col.find({
            "user_id": owner["user_id"],
            "last_turn_at": {"$gte": _now() - __import__('datetime').timedelta(days=3)},
        })) if threads_col is not None else []
        
        for t in recent:
            msgs = t.get("messages", [])
            for m in msgs[-10:]:
                txt = (m.get("text", "") or "").lower()
                # Simple keyword overlap check — does the founder's message reflect
                # the predicted response occurring?
                keywords = set(predicted.split()[:8]) - {"the", "a", "an", "is", "to", "of", "in", "will", "be", "and"}
                matches = sum(1 for kw in keywords if kw in txt)
                if matches >= 3:
                    return True
        
        # Also check if the predicted actor appears positively in recent activity
        actor = (step.get("actor_affected", "") or "").lower()
        if actor:
            for t in recent:
                msgs = t.get("messages", [])
                for m in msgs[-5:]:
                    if actor in (m.get("text", "") or "").lower():
                        return True
    except Exception:
        pass
    
    return False


def _silent_execute_step(org_id: str, chain: dict, step: dict, step_number: int):
    """Auto-execute a chain step without founder interaction. L1-L2 only."""
    try:
        # Check authority: only auto-execute if step has no irreversible actions
        risk = step.get("resource_cost", "").lower()
        if any(w in risk for w in ("legal", "irreversible", "firing", "lawsuit")):
            log.info(f"Chain {chain['id']}: step {step_number} requires manual — skipping auto-execute")
            return  # L3+ — do not auto-execute
        
        result = execute_chain_step(org_id, step, {"actors": chain.get("actors", [])}, chain.get("objective", ""))
        now = _now()
        CAUSAL_CHAINS_COL.update_one(
            {"id": chain["id"]},
            {"$set": {
                f"step_executed_at.{step_number}": now.isoformat(),
                "status": "active",
            }}
        )
        log.info(f"Chain {chain['id']}: step {step_number} auto-executed — {step.get('action', '')[:80]}")
    except Exception as e:
        log.warning(f"Chain {chain['id']}: step {step_number} auto-execute failed: {e}")


def _trigger_fallback(org_id: str, chain: dict, failed_step: dict):
    """Prediction failed — trigger the fallback plan for this chain."""
    fallback = chain.get("alternative_chain", "")
    critical = chain.get("critical_chain_link", "")
    
    CAUSAL_CHAINS_COL.update_one(
        {"id": chain["id"]},
        {"$set": {
            "status": "fallback_triggered",
            "failed_at_step": failed_step.get("step"),
            "failure_reason": f"Predicted response '{failed_step.get('predicted_response', '')[:100]}' did not occur",
            "fallback_activated_at": _now(),
        }}
    )
    
    # Create an alert task for the founder
    try:
        if tasks_col is not None:
            owner = members_col.find_one({"org_id": org_id, "role": "owner"}) if members_col is not None else None
            if owner:
                tasks_col.insert_one({
                    "id": _uid(), "org_id": org_id, "plan_id": "",
                    "department_function": "strategy",
                    "title": f"[SALAAR] Chain '{chain.get('chain_name', '')}' hit a wall at step {failed_step.get('step')}",
                    "description": f"Predicted response did not occur. Fallback: {fallback or 'Manual review needed'}.\nCritical link: {critical}",
                    "assigned_to": owner["user_id"], "assigned_to_name": "Founder",
                    "status": "pending",
                    "due_at": None, "week_start": None,
                    "generated_week": _now().isocalendar()[1],
                    "proof_files": [],
                    "ai_review": {"status": "auto_generated", "notes": "SALAAR fallback trigger", "confidence": 0.9, "reviewed_at": _now().isoformat()},
                    "stage": {"label": "not_started", "confidence": 1.0, "last_updated": _now().isoformat()},
                    "escalation": {"dept_head_contacted": False, "dept_head_response": "", "founder_contacted": True, "founder_response": "", "escalated_at": _now().isoformat()},
                    "created_at": _now().isoformat(), "updated_at": _now().isoformat(), "completed_at": None,
                })
    except Exception:
        pass
    
    log.warning(f"Chain {chain['id']}: fallback triggered at step {failed_step.get('step')}")


# Close out a chain with its resolution reason.
def _mark_chain_resolved(chain_id: str, reason: str):
    CAUSAL_CHAINS_COL.update_one(
        {"id": chain_id},
        {"$set": {"status": "resolved", "resolved_at": _now(), "resolution_reason": reason}}
    )


# ======================================================================
# AUTOMATION 3: Cron-wired chain auto-advancer for all active orgs
# ======================================================================

def auto_advance_all_chains():
    """Run across all orgs with active chains. Called every 15 min by SALAAR deep scan."""
    total_advanced = 0
    total_fallbacks = 0
    try:
        for org in orgs_col.find({}, {"_id": 0, "id": 1, "name": 1}) if orgs_col is not None else []:
            try:
                r = auto_advance_chains(org["id"])
                total_advanced += r.get("advanced", 0)
                total_fallbacks += r.get("fallbacks_triggered", 0)
            except Exception as e:
                log.debug(f"SALAAR chain auto-advance: org {org.get('id')} skipped: {e}")
    except Exception as e:
        log.exception(f"SALAAR chain auto-advance global failure: {e}")
    
    if total_advanced > 0 or total_fallbacks > 0:
        log.info(f"SALAAR chain auto-advance: {total_advanced} advanced, {total_fallbacks} fallbacks across all orgs")
    return {"advanced": total_advanced, "fallbacks_triggered": total_fallbacks}

