"""
Mission Context Engine — cached assembly of organizational context.

Assembles once per thread/session: Mission → Goals → Capabilities → context block.
Feeds into the LLM prompt so SALAAR reasons with full organizational awareness.
Zero per-turn LLM cost after initial assembly.
"""

import json
import logging


log = logging.getLogger("execution.mission_context")


def assemble_mission_context(
    org_id: str = None,
    user_id: str = None,
    org_data: dict = None,
    executives: list[dict] = None,
    thread_data: dict = None,
) -> dict:
    """Build the mission context block for SALAAR.

    Returns a dict ready to inject into the LLM system prompt.
    """
    context = {
        "mission": "",
        "north_star": "",
        "strategy": {},
        "active_goals": [],
        "executive_roster": [],
        "capabilities_available": [],
        "recent_evidence": [],
        "org_health": "unknown",
    }

    # ── Organization-level context ──
    if org_data:
        context["north_star"] = org_data.get("north_star", "")
        context["mission"] = org_data.get("mission", context["north_star"])
        context["strategy"] = {
            "target": org_data.get("target", ""),
            "deadline": org_data.get("deadline", ""),
            "priorities": org_data.get("priorities", []),
            "decision_rules": org_data.get("decision_rules", ""),
        }
        context["current_arr"] = org_data.get("current_arr")
        context["target_arr"] = org_data.get("target_arr")

    # ── Executive roster ──
    if executives:
        for ex in executives:
            context["executive_roster"].append({
                "id": ex.get("id", ""),
                "role": ex.get("role", ""),
                "department": ex.get("department_id", ""),
                "status": ex.get("lifecycle", {}).get("status", ""),
                "mission": ex.get("mission", ""),
                "kpis": [{"name": k.get("name", ""), "target": k.get("target", "")}
                         for k in (ex.get("kpis") or [])[:3]],
                "budget": ex.get("budget", {}).get("allocated_inr", 0),
                "authority": ex.get("authority", {}).get("spending_limit_inr", 0),
                "active_projects": ex.get("current_state", {}).get("active_projects", []),
            })

    # ── Thread context ──
    if thread_data:
        context["active_goals"].append({
            "goal": thread_data.get("goal", ""),
            "why_now": thread_data.get("why_now", ""),
            "phase": thread_data.get("current_phase", ""),
            "next_action": thread_data.get("current_next_action", ""),
            "open_question": thread_data.get("current_open_question", ""),
        })

    # ── Determine org health ──
    active_execs = sum(1 for e in (executives or [])
                       if e.get("lifecycle", {}).get("status") in ("active", "probation"))
    context["org_health"] = (
        "healthy" if active_execs >= 2 else
        "minimal" if active_execs == 1 else
        "not_configured"
    )

    return context


def mission_context_block(context: dict) -> str:
    """Render the mission context as a prompt-safe text block for the LLM."""
    lines = []

    if context.get("north_star"):
        lines.append(f"COMPANY NORTH STAR: {context['north_star']}")

    strat = context.get("strategy", {})
    if strat.get("target"):
        lines.append(f"TARGET: {strat['target']} by {strat.get('deadline', 'TBD')}")
    if strat.get("priorities"):
        lines.append(f"PRIORITIES: {'; '.join(strat['priorities'][:5])}")
    if strat.get("decision_rules"):
        lines.append(f"DECISION RULES: {strat['decision_rules']}")

    lines.append(f"ORG HEALTH: {context.get('org_health', 'unknown')}")

    execs = context.get("executive_roster", [])
    if execs:
        lines.append(f"\nEXECUTIVE ROSTER ({len(execs)} members):")
        for e in execs[:10]:
            kpi_str = ", ".join(f"{k['name']}:{k['target']}" for k in e.get("kpis", [])[:2])
            lines.append(f"  - {e['role']} ({e['department']}, {e['status']}): {e['mission'][:100]}")
            if kpi_str:
                lines.append(f"    KPIs: {kpi_str}")

    goals = context.get("active_goals", [])
    if goals:
        for g in goals:
            lines.append(f"\nACTIVE GOAL: {g['goal']}")
            lines.append(f"  Phase: {g['phase']} | Question: {g.get('open_question', '')}")

    return "\n".join(lines)


# ── Demo ──
def _demo():
    ctx = assemble_mission_context(
        org_data={
            "north_star": "Make every Indian SME founder 2x more decisive",
            "target": "500 paying founders",
            "deadline": "Dec 2027",
            "priorities": ["Ship Capability Registry", "Onboard 50 beta founders"],
            "decision_rules": "Ship after 3 founder conversations validate the problem",
        },
        executives=[
            {
                "id": "e1", "role": "VP Growth", "department_id": "marketing",
                "mission": "Acquire 500 founders via content",
                "lifecycle": {"status": "active"},
                "kpis": [{"name": "Signups", "target": "50/month"}],
                "authority": {"spending_limit_inr": 200000},
            },
            {
                "id": "e2", "role": "VP Engineering", "department_id": "engineering",
                "mission": "Ship Capability Registry",
                "lifecycle": {"status": "probation"},
                "kpis": [{"name": "Deploy freq", "target": "daily"}],
                "authority": {"spending_limit_inr": 500000},
            },
        ],
        thread_data={"goal": "Launch MVP", "why_now": "Window is open", "current_phase": "exploring",
                      "current_open_question": "What to validate first?"},
    )

    block = mission_context_block(ctx)
    return {"context_keys": list(ctx.keys()), "block_lines": len(block.split("\n")), "block_preview": block[:300] + "..."}


if __name__ == "__main__":
    print(json.dumps(_demo(), indent=2, default=str))
