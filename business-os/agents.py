"""Multi-Agent System — persistent AI executives that operate continuously.

Each agent has: role, mission, KPIs, authority level, schedule, memory.
Agents detect → decide → execute → verify → learn → escalate.

Architecture:
  Agent Runtime: runs on schedule, makes decisions within authority
  Cross-Agent Bus: agents share signals for emergent coordination  
  Founder Inbox: escalated items when agent hits authority boundary

Uses existing: execution runtime, system model, OKR engine, verification, tools.
"""
import json
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db as _db
from llm_client import client as llm_client, _extract_json

log = logging.getLogger("agents")

AGENTS_COL = _db.agents if _db is not None else None
INBOX_COL = _db.agent_inbox if _db is not None else None
SIGNALS_COL = _db.agent_signals if _db is not None else None

if AGENTS_COL is not None:
    AGENTS_COL.create_index("id", unique=True)
    AGENTS_COL.create_index([("org_id", 1), ("status", 1)])
if INBOX_COL is not None:
    INBOX_COL.create_index([("org_id", 1), ("status", 1)])
    INBOX_COL.create_index([("org_id", 1), ("created_at", -1)])
if SIGNALS_COL is not None:
    SIGNALS_COL.create_index([("org_id", 1), ("created_at", -1)])

# Agent authority ladder and schedule cadence (minutes)
AUTHORITY_LEVELS = {"L1": "observe", "L2": "alert_only", "L3": "execute_reversible",
                     "L4": "execute_with_approval", "L5": "founder_only"}
SCHEDULES = {"realtime": 5, "hourly": 60, "daily": 1440, "weekly": 10080}


# Return current UTC-aware timestamp
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# Agent definitions — 8 agent types, each with mission + triggers
# ======================================================================

AGENT_DEFINITIONS = {
    "strategy_agent": {
        "role": "Strategy Agent",
        "mission": "Monitor market shifts, competitor moves, and strategic opportunities. Alert founder to inflection points.",
        "kpis": ["competitor_alerts_generated", "strategy_memos_produced", "opportunities_flagged"],
        "schedule": "weekly",
        "authority": "L3",
        "functions": ["strategy", "vision"],
        "decision_prompt": """You are the Strategy Agent for this company. Review the company's current state, recent signals, and market context. Decide: is there a strategic action worth taking?

Return ONLY JSON:
{"action": "ALERT"|"DRAFT_MEMO"|"NOTHING",
 "severity": "high"|"medium"|"low",
 "summary": "one-line insight for the founder",
 "recommendation": "what they should do",
 "needs_founder": true if this requires founder decision}""",
    },
    "growth_agent": {
        "role": "Growth Agent",  
        "mission": "Identify growth bottlenecks, suggest experiments, track CAC/LTV/churn trends.",
        "kpis": ["growth_experiments_proposed", "bottlenecks_identified", "metric_alerts"],
        "schedule": "daily",
        "authority": "L3",
        "functions": ["growth", "marketing", "sales", "data"],
        "decision_prompt": """You are the Growth Agent. Review growth metrics, experiment results, and bottlenecks. What's the highest-leverage growth action right now?

Return ONLY JSON:
{"action": "ALERT"|"PROPOSE_EXPERIMENT"|"ESCALATE_BOTTLENECK"|"NOTHING",
 "metric_affected": "CAC|LTV|churn|conversion|retention|other",
 "summary": "what the numbers say",
 "recommendation": "specific experiment or fix",
 "needs_founder": true if this needs budget or strategic approval}""",
    },
    "customer_agent": {
        "role": "Customer Success Agent",
        "mission": "Detect churn signals, trigger interventions, monitor NPS and health scores.",
        "kpis": ["churn_alerts", "interventions_triggered", "accounts_saved"],
        "schedule": "realtime",
        "authority": "L3",
        "functions": ["customer_success"],
        "decision_prompt": """You are the Customer Success Agent. Review customer health signals. Any account needs intervention?

Return ONLY JSON:
{"action": "INTERVENE"|"ALERT"|"NOTHING",
 "customer_count": number of at-risk accounts,
 "top_risk": "name or description of highest-risk account",
 "intervention": "what email/message/call to make",
 "needs_founder": true if annual contract value > 20% of ARR}""",
    },
    "ops_agent": {
        "role": "Operations Agent",
        "mission": "Track task completion, flag overdue items, monitor OKR progress, keep execution on track.",
        "kpis": ["overdue_flagged", "okr_stalling_detected", "tasks_auto_closed"],
        "schedule": "daily",
        "authority": "L3",
        "functions": ["operations", "hr"],
        "decision_prompt": """You are the Operations Agent. Review task queue, OKR progress, and team velocity. What needs attention?

Return ONLY JSON:
{"action": "ALERT"|"ESCALATE"|"CLOSE_STALE"|"NOTHING",
 "overdue_count": number,
 "stalling_okrs": ["OKR descriptions"],
 "summary": "what's blocked or falling behind",
 "recommendation": "what to do",
 "needs_founder": true if this involves personnel decisions}""",
    },
    "finance_agent": {
        "role": "Finance Agent",
        "mission": "Track cash flow, burn rate, runway. Flag budget overruns. Prepare investor updates.",
        "kpis": ["cash_alerts", "budget_violations_flagged", "investor_updates_drafted"],
        "schedule": "weekly",
        "authority": "L2",
        "functions": ["finance"],
        "decision_prompt": """You are the Finance Agent. Review cash position, burn rate, and budget utilization. Any concerns?

Return ONLY JSON:
{"action": "ALERT"|"DRAFT_UPDATE"|"FLAG_OVERSPEND"|"NOTHING",
 "runway_months": number,
 "burn_rate": monthly burn,
 "alerts": ["specific financial concerns"],
 "recommendation": "what the founder should do about money",
 "needs_founder": true if runway < 6 months or major budget decision}""",
    },
    "tech_agent": {
        "role": "Technology Agent",
        "mission": "Monitor system health, deployment frequency, incident patterns, tech debt signals.",
        "kpis": ["incidents_detected", "tech_debt_alerts", "deploy_health_score"],
        "schedule": "daily",
        "authority": "L3",
        "functions": ["technology"],
        "decision_prompt": """You are the Technology Agent. Review engineering health signals. Any issues?

Return ONLY JSON:
{"action": "ALERT"|"CREATE_TICKET"|"NOTHING",
 "severity": "high"|"medium"|"low",
 "issue": "what's happening",
 "impact": "what it affects",
 "recommended_fix": "what engineering should do",
 "needs_founder": true if it affects customer-facing systems or involves >1 week of engineering time}""",
    },
    "brand_agent": {
        "role": "Brand Agent",
        "mission": "Monitor online reputation, social engagement, PR mentions. Flag reputation risks.",
        "kpis": ["reputation_alerts", "engagement_trends", "crisis_escalations"],
        "schedule": "daily",
        "authority": "L2",
        "functions": ["brand", "marketing"],
        "decision_prompt": """You are the Brand Agent. Any reputation or engagement concerns?

Return ONLY JSON:
{"action": "ALERT"|"DRAFT_RESPONSE"|"NOTHING",
 "platform": "where the issue is",
 "sentiment": "positive|neutral|negative|critical",
 "summary": "what's happening",
 "suggested_response": "what to say or do",
 "needs_founder": true if this is a potential crisis or involves legal risk}""",
    },
    "sales_agent": {
        "role": "Sales Agent",
        "mission": "Follow up leads, draft proposals, schedule demos, track pipeline health, flag stuck deals.",
        "kpis": ["leads_followed_up", "proposals_drafted", "pipeline_health_score", "stuck_deals_flagged"],
        "schedule": "daily",
        "authority": "L3",
        "functions": ["sales"],
        "decision_prompt": """You are the Sales Agent. Review pipeline data and identify deals needing action.

Return ONLY JSON:
{"action": "FOLLOW_UP_LEADS"|"DRAFT_PROPOSAL"|"FLAG_STUCK_DEAL"|"ALERT"|"NOTHING",
 "deal_count": number of active deals,
 "stuck_count": deals with no activity in 14 days,
 "top_action": "what single action would move the needle most",
 "recommendation": "specific next step",
 "auto_send": true if you should auto-send a follow-up email (L3 authority, reversible),
 "needs_founder": true if this involves pricing changes or enterprise deals > 20% of ARR}""",
    },
    "marketing_agent": {
        "role": "Marketing Agent",
        "mission": "Monitor campaign performance, suggest budget shifts, generate content ideas, track channel ROI.",
        "kpis": ["campaign_alerts", "budget_recommendations", "content_suggestions", "channel_roi_trends"],
        "schedule": "daily",
        "authority": "L3",
        "functions": ["marketing", "brand", "growth"],
        "decision_prompt": """You are the Marketing Agent. Review campaign metrics and channel performance.

Return ONLY JSON:
{"action": "ALERT"|"SUGGEST_SHIFT"|"GENERATE_CONTENT"|"NOTHING",
 "top_channel": "channel with highest ROI",
 "worst_channel": "channel losing money",
 "recommendation": "where to move budget",
 "content_idea": "one content idea that would resonate",
 "needs_founder": true if suggesting budget moves > ₹50K or new channel investment}""",
    },
    "hr_agent": {
        "role": "HR Agent",
        "mission": "Track hiring pipeline, flag underperformers, monitor team morale signals, suggest org structure improvements.",
        "kpis": ["hiring_funnel_health", "retention_risks", "org_structure_suggestions", "culture_alerts"],
        "schedule": "weekly",
        "authority": "L2",
        "functions": ["hr", "leadership"],
        "decision_prompt": """You are the HR Agent. Review team health signals and hiring pipeline.

Return ONLY JSON:
{"action": "ALERT"|"DRAFT_JD"|"FLAG_RETENTION_RISK"|"SUGGEST_ORG_CHANGE"|"NOTHING",
 "headcount": total team size,
 "open_roles": roles with open hiring,
 "retention_risks": ["people showing departure signals"],
 "recommendation": "what to do about people",
 "needs_founder": true if this involves firing, senior hiring decisions, or compensation changes}""",
    },
    "product_agent": {
        "role": "Product Agent",
        "mission": "Track feature adoption, flag tech debt vs new feature balance, monitor user feedback patterns, suggest roadmap priorities.",
        "kpis": ["feature_adoption_trends", "tech_debt_ratio", "user_feedback_themes", "roadmap_alerts"],
        "schedule": "weekly",
        "authority": "L3",
        "functions": ["product", "technology"],
        "decision_prompt": """You are the Product Agent. Review feature usage data and engineering velocity.

Return ONLY JSON:
{"action": "ALERT"|"SUGGEST_PRIORITY"|"FLAG_TECH_DEBT"|"CREATE_SPEC"|"NOTHING",
 "top_feature": "most adopted feature this period",
 "dead_features": ["features with <5% adoption"],
 "tech_debt_pct": what % of engineering time goes to tech debt vs features,
 "recommendation": "what should ship next",
 "needs_founder": true if this involves major roadmap changes or resource allocation}""",
    },
    "system_agent": {
        "role": "System Health Agent",
        "mission": "Run daily health scans, detect anomalies across all 16 functions, flag worsening trends.",
        "kpis": ["scans_run", "anomalies_detected", "trend_alerts"],
        "schedule": "daily",
        "authority": "L2",
        "functions": ["vision", "strategy", "leadership", "operations"],
        "decision_prompt": """You are the System Health Agent. Review today's scan vs yesterday's. What changed?

Return ONLY JSON:
{"action": "ALERT"|"GENERATE_TASKS"|"NOTHING",
 "changed_functions": ["functions that moved >10pts"],
 "worsening": ["functions getting worse"],
 "improving": ["functions getting better"],
 "summary": "one-line brief for the founder",
 "needs_founder": true if any function dropped below 40}""",
    },
}


# ======================================================================
# Agent lifecycle
# ======================================================================

def create_agent(org_id: str, agent_type: str, user_id: str = None) -> dict:
    """Create a new agent instance for an org."""
    if agent_type not in AGENT_DEFINITIONS:
        return {"error": f"Unknown agent type: {agent_type}"}

    definition = AGENT_DEFINITIONS[agent_type]
    agent = {
        "id": f"agent_{agent_type}_{org_id[:8]}",
        "org_id": org_id,
        "type": agent_type,
        "role": definition["role"],
        "mission": definition["mission"],
        "kpis": definition["kpis"],
        "schedule": definition["schedule"],
        "authority": definition["authority"],
        "status": "active",
        "functions": definition["functions"],
        "memory": {"decisions_made": 0, "alerts_sent": 0, "actions_taken": 0, "last_action": None, "learnings": []},
        "created_by": user_id,
        "created_at": _now().isoformat(),
        "last_run": None,
        "next_run": _now().isoformat(),
    }

    if AGENTS_COL is not None:
        AGENTS_COL.update_one(
            {"org_id": org_id, "type": agent_type},
            {"$set": agent}, upsert=True,
        )

    log.info(f"Agent created: {agent_type} for org {org_id}")
    return agent


def get_agents(org_id: str) -> list:
    """List all agents for an org."""
    if AGENTS_COL is None:
        return []
    return list(AGENTS_COL.find({"org_id": org_id, "status": "active"}, {"_id": 0}))


# Fetch one active agent by type
def get_agent(org_id: str, agent_type: str) -> Optional[dict]:
    if AGENTS_COL is None:
        return None
    return AGENTS_COL.find_one({"org_id": org_id, "type": agent_type, "status": "active"}, {"_id": 0})


# ======================================================================
# Agent Runtime — the decision loop
# ======================================================================

def run_agent(org_id: str, agent_type: str, context: dict = None) -> dict:
    """Execute one decision cycle for an agent."""
    agent = get_agent(org_id, agent_type)
    if not agent:
        agent = create_agent(org_id, agent_type)
        if "error" in agent:
            return agent

    definition = AGENT_DEFINITIONS.get(agent_type)
    if not definition:
        return {"error": f"No definition for {agent_type}"}

    # Build context from system model + OKRs + cross-agent signals
    ctx = _build_agent_context(org_id, agent, context or {})

    # ── LLM decision via multi-provider smart router ──
    try:
        from llm_router import agent_decision as _agent_call
        result = _agent_call(
            system=definition["decision_prompt"],
            messages=[{"role": "user", "content": ctx}],
        )
        txt = result["text"]
        from llm_client import _extract_json
        decision = json.loads(_extract_json(txt))
        # Store model info for telemetry
        decision["_model"] = result.get("model", "")
        decision["_provider"] = result.get("provider", "")
        decision["_tokens"] = result.get("input_tokens", 0) + result.get("output_tokens", 0)
    except Exception as e:
        log.error(f"Agent {agent_type} decision failed: {e}")
        decision = {"action": "NOTHING", "summary": f"Decision engine error: {str(e)[:100]}", "needs_founder": False, "_model": "fallback", "_provider": "none"}

    # Process the decision
    action = decision.get("action", "NOTHING")
    needs_founder = decision.get("needs_founder", False)
    summary = decision.get("summary", "")
    auto_send = decision.get("auto_send", False)
    severity = decision.get("severity", "medium")

    # Execute based on action
    if action in ("ALERT", "ESCALATE", "FLAG_OVERSPEND") and needs_founder:
        _send_to_inbox(org_id, agent_type, agent["role"], summary, decision.get("recommendation", ""), severity)
        # Also submit to approval inbox so founder can one-tap approve
        try:
            from business_os import request_approval
            request_approval(org_id, agent_type, agent["role"], decision)
        except Exception:
            pass

    # Autonomous external communication: L3 agents with auto_send flag
    if auto_send and definition["authority"] in ("L2", "L3") and not needs_founder:
        _auto_communicate(org_id, agent_type, agent["role"], summary, decision)

    if action in ("GENERATE_TASKS", "CREATE_TICKET", "DRAFT_MEMO", "PROPOSE_EXPERIMENT", "INTERVENE"):
        if definition["authority"] in ("L2", "L3") and not needs_founder:
            _execute_agent_action(org_id, agent_type, agent["role"], action, summary, decision)
            # Schedule outcome verification 24h later
            try:
                from business_os import verify_business_outcome
                verify_business_outcome(
                    f"agent_{agent_type}_{_now().strftime('%Y%m%d%H%M%S')}",
                    org_id, agent_type, summary, actual=None,
                )
            except Exception:
                pass
        else:
            _send_to_inbox(org_id, agent_type, agent["role"], summary, decision.get("recommendation", ""), severity)

    # Autonomous fund management: L3 agents can spend within budgeted limit
    if action in ("SUGGEST_SHIFT", "DRAFT_PROPOSAL") and not needs_founder:
        amount = decision.get("budget_amount", decision.get("amount", 0))
        if 0 < amount <= 5000:  # ponytail: ₹5K auto-spend cap, raise when trust is earned
            _auto_spend(org_id, agent_type, amount, f"[{agent['role']}] {summary[:150]}")

    # Broadcast signal to other agents
    if summary:
        _broadcast_signal(org_id, agent_type, summary)

    # Update agent memory
    _update_agent_memory(org_id, agent_type, action, summary)

    log.info(f"Agent {agent_type}: action={action}, needs_founder={needs_founder}, summary='{summary[:80]}'")

    # ── Audit trail: record every agent decision ──
    try:
        from audit import record_agent_decision
        record_agent_decision(org_id, agent_type, action, summary[:200],
                              model=decision.get("_model", ""))
    except Exception:
        pass

    # ── Quality tracking: update agent stats ──
    _update_agent_quality(org_id, agent_type, action, needs_founder, summary)

    log.info(f"Agent {agent_type}: action={action}, needs_founder={needs_founder}, summary='{summary[:80]}'")
    return {"agent": agent_type, "action": action, "summary": summary, "needs_founder": needs_founder}


# ── Quality tracking ──

def _update_agent_quality(org_id: str, agent_type: str, action: str, needs_founder: bool, summary: str):
    """Track agent decision quality: action rates, escalation rates, decision types."""
    if AGENTS_COL is None:
        return
    inc = {"memory.decisions_made": 1}
    if needs_founder:
        inc["memory.escalations"] = 1
    if action != "NOTHING":
        inc["memory.active_decisions"] = 1
    AGENTS_COL.update_one(
        {"org_id": org_id, "type": agent_type},
        {"$inc": inc},
    )


def get_agent_quality(org_id: str) -> dict:
    """Quality metrics per agent: action rate, escalation rate, decision distribution."""
    agents = get_agents(org_id)
    result = {}
    for a in agents:
        mem = a.get("memory", {})
        total = mem.get("decisions_made", 0) or 1
        escalations = mem.get("escalations", 0) or 0
        active = mem.get("active_decisions", 0) or 0
        actions = mem.get("actions_taken", 0) or 0
        result[a["type"]] = {
            "role": a.get("role", ""),
            "total_decisions": total,
            "active_decisions": active,
            "action_rate_pct": round(100 * active / total, 1),
            "escalation_rate_pct": round(100 * escalations / total, 1),
            "auto_actions": actions,
            "autonomy_score": round(100 * actions / max(total, 1), 1),
        }
    return result


# ── Cross-agent coordination enrichment ──

COORDINATION_MAP = {
    "sales_agent": {"ask": ["customer_agent", "finance_agent"],
                     "reason": "Check customer health and payment history before any deal action"},
    "customer_agent": {"ask": ["sales_agent", "ops_agent"],
                        "reason": "Check deal status and recent interactions before intervention"},
    "growth_agent": {"ask": ["marketing_agent", "sales_agent"],
                      "reason": "Check campaign performance and pipeline before growth recommendations"},
    "marketing_agent": {"ask": ["growth_agent", "brand_agent"],
                         "reason": "Check growth experiments and brand sentiment before budget shifts"},
    "finance_agent": {"ask": ["sales_agent", "ops_agent"],
                       "reason": "Check pipeline and operational spending before financial alerts"},
    "ops_agent": {"ask": ["hr_agent", "tech_agent"],
                   "reason": "Check team capacity and system health before operational decisions"},
    "hr_agent": {"ask": ["ops_agent", "finance_agent"],
                  "reason": "Check workload and budget before people recommendations"},
    "product_agent": {"ask": ["tech_agent", "customer_agent"],
                       "reason": "Check tech debt and customer feedback before roadmap decisions"},
    "tech_agent": {"ask": ["product_agent", "ops_agent"],
                    "reason": "Check roadmap priorities and ops load before tech decisions"},
    "strategy_agent": {"ask": ["finance_agent", "growth_agent"],
                        "reason": "Check financial health and growth trajectory before strategy moves"},
    "brand_agent": {"ask": ["marketing_agent", "customer_agent"],
                     "reason": "Check campaigns and customer sentiment before brand actions"},
    "system_agent": {"ask": [],
                      "reason": "System agent sees all — coordinates through signal bus"},
}


def _enrich_with_coordination(org_id: str, agent_type: str, lines: list[str]):
    """Enrich agent context with what related agents have detected.
    Sales should know what Customer agents see about the customer before acting."""
    coord = COORDINATION_MAP.get(agent_type)
    if not coord or not coord["ask"]:
        return
    lines.append(f"\nCOORDINATION: Before deciding, check what these agents know ({coord['reason']}):")
    for related_type in coord["ask"]:
        related = get_agent(org_id, related_type)
        if related:
            last = related.get("memory", {}).get("last_action", "")
            lines.append(f"  - {related.get('role', related_type)} last action: {last[:120]}")
            # Also get recent signals specifically from this agent
            try:
                if SIGNALS_COL:
                    sig = list(SIGNALS_COL.find(
                        {"org_id": org_id, "from_agent": related_type},
                    ).sort("created_at", -1).limit(2))
                    for s in sig:
                        lines.append(f"    → Signal: {s.get('message', '')[:120]}")
            except Exception:
                pass


def _build_agent_context(org_id: str, agent: dict, extra: dict) -> str:
    """Build the context string for an agent's LLM decision."""
    lines = [f"AGENT: {agent['role']}", f"MISSION: {agent['mission']}", f"AUTHORITY: {agent['authority']}",
             f"RECENT ACTIONS: {agent['memory']['decisions_made']} decisions, {agent['memory']['actions_taken']} actions"]

    # System model health
    try:
        from business_system import get_system_model
        sm = get_system_model(org_id) or {}
        functions = sm.get("functions", {})
        funcs = agent.get("functions", [])
        relevant = {f: s for f, s in functions.items() if f in funcs}
        if relevant:
            lines.append("YOUR FUNCTIONS:")
            for f, s in relevant.items():
                lines.append(f"  {f}: {s['health']}/100 ({s['status']})")
    except Exception:
        pass

    # OKR health
    try:
        from okr_engine import okr_health_report
        okr = okr_health_report(org_id)
        if okr.get("total_krs"):
            lines.append(f"OKR HEALTH: {okr['on_track']}/{okr['total_krs']} on track, {okr['stalling']} stalling, {okr['at_risk']} at risk")
    except Exception:
        pass

    # Recent signals from other agents — consume + coordinate
    try:
        if SIGNALS_COL:
            signals = list(SIGNALS_COL.find({"org_id": org_id}).sort("created_at", -1).limit(8))
            if signals:
                lines.append("RECENT SIGNALS FROM OTHER AGENTS (coordinate your decision with these):")
                for s in signals:
                    # Mark signal as consumed
                    SIGNALS_COL.update_one({"id": s["id"]}, {"$set": {"consumed_by": agent_type, "consumed_at": _now().isoformat()}})
                    lines.append(f"  [{s['from_agent']}]: {s['message'][:150]}")
                lines.append("If another agent already acted on this issue, do NOT duplicate. Coordinate: who owns what.")
    except Exception:
        pass

    # Extra context
    for k, v in extra.items():
        if v:
            lines.append(f"{k.upper()}: {str(v)[:300]}")

    # Cross-agent coordination enrichment
    _enrich_with_coordination(org_id, agent_type, lines)

    return "\n".join(lines)


def _send_to_inbox(org_id, agent_type, role, summary, recommendation, severity):
    """Escalate to founder inbox."""
    if INBOX_COL is None:
        return
    item = {
        "id": f"inbox_{uuid.uuid4().hex[:12]}",
        "org_id": org_id,
        "from_agent": agent_type,
        "from_role": role,
        "summary": summary[:300],
        "recommendation": recommendation[:300],
        "severity": severity,
        "status": "unread",
        "created_at": _now().isoformat(),
    }
    INBOX_COL.insert_one(item)
    _update_agent_counter(org_id, agent_type, "alerts_sent")


def _execute_agent_action(org_id, agent_type, role, action, summary, decision):
    """Execute an agent's decision via the execution runtime."""
    try:
        from execution.bridge import enqueue_engine_action
        enqueue_engine_action(org_id, {
            "description": f"[{role}] {summary[:180]}",
            "capability": agent_type.replace("_agent", ""),
            "expected_outcome": decision.get("recommendation", "Action completed")[:200],
            "reversibility": "REVERSIBLE",
            "authority_required": "L3",
        })
        _update_agent_counter(org_id, agent_type, "actions_taken")
    except Exception as e:
        log.warning(f"Agent {agent_type} action execution failed: {e}")


def _broadcast_signal(org_id, from_agent, message):
    """Share a signal to other agents."""
    if SIGNALS_COL is None:
        return
    SIGNALS_COL.insert_one({
        "id": f"sig_{uuid.uuid4().hex[:12]}",
        "org_id": org_id,
        "from_agent": from_agent,
        "message": message[:300],
        "created_at": _now().isoformat(),
    })


def _update_agent_memory(org_id, agent_type, action, summary):
    """Update agent's memory counters and learnings."""
    if AGENTS_COL is None:
        return
    AGENTS_COL.update_one(
        {"org_id": org_id, "type": agent_type},
        {"$inc": {"memory.decisions_made": 1},
         "$set": {"memory.last_action": f"{action}: {summary[:150]}", "last_run": _now().isoformat()}},
    )


# Increment an agent's memory counter
def _update_agent_counter(org_id, agent_type, field):
    if AGENTS_COL is None:
        return
    AGENTS_COL.update_one({"org_id": org_id, "type": agent_type}, {"$inc": {f"memory.{field}": 1}})


def _auto_communicate(org_id, agent_type, role, summary, decision):
    """Autonomous external communication via connected tools (L3 agents only)."""
    try:
        recommendation = decision.get("recommendation", summary[:200])
        from execution.bridge import enqueue_engine_action
        enqueue_engine_action(org_id, {
            "description": f"[{role}] {summary[:180]}",
            "capability": agent_type.replace("_agent", ""),
            "expected_outcome": recommendation[:200],
            "reversibility": "REVERSIBLE",
            "authority_required": "L3",
        })
        _update_agent_counter(org_id, agent_type, "actions_taken")
        log.info(f"Agent {agent_type}: auto-communicate — {summary[:80]}")
    except Exception as e:
        log.warning(f"Auto-communicate failed for {agent_type}: {e}")


def _auto_spend(org_id, agent_type, amount_inr, description):
    """Autonomous fund management within budgeted limits."""
    try:
        from execution.bridge import enforce_budget, record_spend
        if enforce_budget(org_id, amount_inr):
            record_spend(org_id, amount_inr)
            log.info(f"Agent {agent_type}: auto-spend ₹{amount_inr} — {description[:80]}")
        else:
            _send_to_inbox(org_id, agent_type, f"{AGENT_DEFINITIONS[agent_type]['role']}",
                          f"Attempted auto-spend of ₹{amount_inr} — budget exceeded", description, "high")
    except Exception as e:
        log.warning(f"Auto-spend failed for {agent_type}: {e}")


# ======================================================================
# Cross-org learning — shared agent memory across orgs
# ======================================================================

def _shared_learning_pattern(agent_type, action, summary, org_id):
    """Detect patterns that repeat across orgs. Store as shared learning."""
    # ponytail: simplified — in production, use a shared embeddings DB
    try:
        key = f"pattern_{agent_type}_{action}"
        count = 1
        existing = SIGNALS_COL.find_one({"org_id": "shared", "from_agent": key}) if SIGNALS_COL else None
        if existing:
            count = existing.get("count", 0) + 1
        if SIGNALS_COL:
            SIGNALS_COL.update_one(
                {"org_id": "shared", "from_agent": key},
                {"$set": {"message": summary[:300], "count": count, "last_seen": _now().isoformat()}},
                upsert=True,
            )
        return count
    except Exception:
        return 0


# ======================================================================
# Agent self-organization — agents can suggest new agents
# ======================================================================

def _check_self_organization(org_id):
    """Agents review the system and suggest creating/retiring agents."""
    agents = get_agents(org_id)
    if len(agents) < 4:
        return

    # Check for gaps: if a function is at-risk and has no dedicated agent, suggest one
    try:
        from business_system import get_system_model
        sm = get_system_model(org_id) or {}
        functions = sm.get("functions", {})

        covered = set()
        for a in agents:
            for f in a.get("functions", []):
                covered.add(f)

        at_risk_uncovered = []
        for f, s in functions.items():
            if s.get("status") == "at_risk" and f not in covered:
                at_risk_uncovered.append(f)

        if at_risk_uncovered:
            _send_to_inbox(org_id, "system_agent", "System",
                          f"Uncovered at-risk functions: {', '.join(at_risk_uncovered[:3])}. "
                          f"Consider creating agents for these domains.",
                          "Review and create agents if needed", "low")
    except Exception:
        pass


# ======================================================================
# Agent orchestration — run all agents for an org
# ======================================================================

def run_all_agents(org_id: str) -> dict:
    """Run all active agents for an org. Called by cron."""
    agents = get_agents(org_id)
    if not agents:
        # Auto-create all 12 agents for the org
        for atype in AGENT_DEFINITIONS:
            create_agent(org_id, atype)
        agents = get_agents(org_id)

    results = {}
    for agent in agents:
        atype = agent["type"]
        # Check if it's time to run based on schedule
        schedule_min = SCHEDULES.get(agent["schedule"], 1440)
        last_run = agent.get("last_run")
        should_run = True
        if last_run:
            try:
                last = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                elapsed = (_now() - last).total_seconds() / 60
                should_run = elapsed >= schedule_min
            except Exception:
                should_run = True

        if should_run:
            try:
                result = run_agent(org_id, atype)
                results[atype] = result
            except Exception as e:
                log.error(f"Agent {atype} failed: {e}")
                results[atype] = {"error": str(e)[:100]}

    # Cross-org learning: detect patterns repeating across orgs
    for atype, result in results.items():
        if isinstance(result, dict) and result.get("summary"):
            _shared_learning_pattern(atype, result.get("action", ""), result["summary"], org_id)

    # Self-organization: agents review coverage gaps
    _check_self_organization(org_id)

    return {"org_id": org_id, "agents_run": len(results), "results": results}


# ======================================================================
# Founder Inbox
# ======================================================================

def get_inbox(org_id: str, status: str = "unread") -> list:
    """Get founder's escalation inbox."""
    if INBOX_COL is None:
        return []
    return list(INBOX_COL.find(
        {"org_id": org_id, "status": status}, {"_id": 0}
    ).sort("created_at", -1).limit(50))


def mark_inbox_item(item_id: str, action: str = "read", founder_note: str = ""):
    """Mark inbox item as read/archived with optional note."""
    if INBOX_COL is None:
        return
    INBOX_COL.update_one({"id": item_id}, {"$set": {
        "status": action,
        "founder_note": founder_note[:200],
        "actioned_at": _now().isoformat(),
    }})


# Aggregate founder inbox counts
def inbox_summary(org_id: str) -> dict:
    if INBOX_COL is None:
        return {"unread": 0}
    return {
        "unread": INBOX_COL.count_documents({"org_id": org_id, "status": "unread"}),
        "total_today": INBOX_COL.count_documents({"org_id": org_id, "created_at": {"$gte": (_now() - timedelta(days=1)).isoformat()}}),
        "by_severity": {
            "high": INBOX_COL.count_documents({"org_id": org_id, "status": "unread", "severity": "high"}),
            "medium": INBOX_COL.count_documents({"org_id": org_id, "status": "unread", "severity": "medium"}),
        },
    }


# ======================================================================
# API Router
# ======================================================================

from fastapi import APIRouter, HTTPException, Depends
from security import current_user
from db import members_col

# Router for agent control endpoints
agent_router = APIRouter(prefix="/api/agents", tags=["agents"])


# Resolve the caller's org from membership
def _get_org_id(user):
    m = members_col.find_one({"user_id": user["id"], "status": "active"})
    if not m:
        raise HTTPException(403, "Not in an organization")
    return m["org_id"]


# List active agents and available types
@agent_router.get("")
def list_agents(user: dict = Depends(current_user)):
    org_id = _get_org_id(user)
    return {"agents": get_agents(org_id), "definitions": list(AGENT_DEFINITIONS.keys())}


# Trigger all agents immediately
@agent_router.post("/run")
def run_agents_now(user: dict = Depends(current_user)):
    org_id = _get_org_id(user)
    return run_all_agents(org_id)


# Run one agent's decision cycle
@agent_router.post("/{agent_type}/run")
def run_single_agent(agent_type: str, user: dict = Depends(current_user)):
    org_id = _get_org_id(user)
    return run_agent(org_id, agent_type)


# Fetch founder escalation inbox
@agent_router.get("/inbox")
def get_founder_inbox(user: dict = Depends(current_user)):
    org_id = _get_org_id(user)
    return {"inbox": get_inbox(org_id), "summary": inbox_summary(org_id)}


# Mark inbox item read or archived
@agent_router.post("/inbox/{item_id}")
def action_inbox_item(item_id: str, body: dict, user: dict = Depends(current_user)):
    mark_inbox_item(item_id, body.get("action", "read"), body.get("note", ""))
    return {"ok": True}


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    assert len(AGENT_DEFINITIONS) == 12, f"Expected 12 agents, got {len(AGENT_DEFINITIONS)}"
    assert all("decision_prompt" in d for d in AGENT_DEFINITIONS.values())
    assert all("authority" in d for d in AGENT_DEFINITIONS.values())
    print("OK — multi-agent system verified")
