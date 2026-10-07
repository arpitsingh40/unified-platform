"""
Tool Intelligence Engine — deterministic tool selection.

select_best_tool(capability, executive_context) → (action, score, fallbacks)

Scoring: availability × permission × cost × reliability × history.
No LLM required. Cold-start priors from catalog metadata.
"""

import logging

from .registry import find

log = logging.getLogger("execution.tie")

# ── Scoring weights ──
WEIGHTS = {
    "availability": 0.35,   # is the toolkit connected?
    "reliability": 0.25,    # historical success rate
    "cost": 0.20,           # lower cost = higher score
    "permission": 0.15,     # does the executive have authority?
    "latency": 0.05,        # faster = higher score
}

# ── Historical tool performance (in-memory for now, moves to DB in production) ──
_tool_scores: dict[str, dict] = {}  # tool_slug → {success, failure, avg_latency_ms}


def record_outcome(tool_slug: str, success: bool, latency_ms: int = 0):
    """Update tool reliability score after execution."""
    if tool_slug not in _tool_scores:
        _tool_scores[tool_slug] = {"success": 0, "failure": 0, "avg_latency_ms": 0}
    s = _tool_scores[tool_slug]
    if success:
        s["success"] += 1
    else:
        s["failure"] += 1
    if latency_ms > 0:
        n = s["success"] + s["failure"]
        s["avg_latency_ms"] = (s["avg_latency_ms"] * (n - 1) + latency_ms) / n if n > 1 else latency_ms


def _reliability_score(tool_slug: str) -> float:
    """0.0–1.0 based on historical success rate. Cold start = 0.5."""
    if tool_slug not in _tool_scores:
        return 0.5
    s = _tool_scores[tool_slug]
    total = s["success"] + s["failure"]
    return s["success"] / total if total > 0 else 0.5


def _cost_score(tool_slug: str, tool_info: dict) -> float:
    """Lower cost = higher score. Estimate from toolkit metadata."""
    cost = tool_info.get("cost_estimate", 0)
    if cost <= 0:
        return 0.8  # free/unknown → good
    if cost < 0.01:
        return 0.9
    if cost < 0.10:
        return 0.7
    if cost < 1.0:
        return 0.5
    return 0.2  # expensive


def _availability_score(tool_info: dict) -> float:
    """Is this toolkit connected? Managed apps get bonus."""
    toolkit = tool_info.get("toolkit", "").lower()
    connected = tool_info.get("connected", False)
    managed = tool_info.get("managed", False)

    if connected:
        return 0.9
    if managed:
        return 0.5  # manageable but needs connection
    return 0.1  # unknown/community toolkit


def _permission_score(tool_slug: str, executive_context: dict) -> float:
    """Does the executive have authority and budget for this tool?"""
    authority = executive_context.get("authority_level", "L1")
    budget = executive_context.get("budget_limit", 0)
    tool_cost = executive_context.get("tool_cost_estimate", 0)

    if authority == "L5":
        return 0.0  # restricted — can't execute
    if authority in ("L4",):
        return 0.3  # needs founder approval
    if budget > 0 and tool_cost > budget:
        return 0.2  # over budget
    if authority in ("L1", "L2"):
        return 0.9  # trusted execution
    return 0.6  # L3 recommend


def select_best_tool(capability: str, executive_context: dict = None, limit: int = 5) -> dict:
    """Find and rank the best tool for a capability.

    Returns: {
        "best": {tool_slug, tool_name, score, confidence},
        "alternatives": [{...}, ...],
        "capability": capability,
    }
    """
    if executive_context is None:
        executive_context = {}

    tools = find(capability)
    if not tools:
        return {"best": None, "alternatives": [], "capability": capability, "error": "no_tools_found"}

    scored = []
    for t in tools:
        slug = t["tool_slug"]
        # Enrich with availability data
        t["connected"] = executive_context.get("connected_toolkits", {}).get(t.get("toolkit", "").lower(), False)
        t["managed"] = executive_context.get("managed_toolkits", {}).get(t.get("toolkit", "").lower(), False)

        score = (
            WEIGHTS["availability"] * _availability_score(t) +
            WEIGHTS["reliability"] * _reliability_score(slug) +
            WEIGHTS["cost"] * _cost_score(slug, t) +
            WEIGHTS["permission"] * _permission_score(slug, executive_context) +
            WEIGHTS["latency"] * 0.5  # neutral default
        )
        scored.append({
            "tool_slug": slug,
            "tool_name": t["tool_name"],
            "toolkit": t.get("toolkit", ""),
            "score": round(score, 3),
            "confidence": round(score, 2),
        })

    scored.sort(key=lambda x: -x["score"])
    best = scored[0] if scored else None
    alternatives = scored[1:limit] if len(scored) > 1 else []

    return {
        "best": best,
        "alternatives": alternatives,
        "capability": capability,
    }


# ── Demo ──
def _demo():
    from .registry import _load_catalog
    _load_catalog()

    ctx = {
        "authority_level": "L1",
        "budget_limit": 50000,
        "connected_toolkits": {"gmail": True},
        "managed_toolkits": {},
    }

    tests = {}
    for cap in ["send_email", "book_meeting", "code_review", "process_payment"]:
        result = select_best_tool(cap, ctx)
        tests[cap] = {
            "best": result["best"]["tool_slug"] if result["best"] else None,
            "score": result["best"]["score"] if result["best"] else 0,
            "alternatives": len(result["alternatives"]),
        }

    return {"tie_results": tests, "status": "OK"}


if __name__ == "__main__":
    import json
    print(json.dumps(_demo(), indent=2, default=str))
