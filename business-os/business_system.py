"""Business System Model — the living graph of a company across 15 interconnected functions.

System Model: dependency graph with per-function state + health scores, built from journey data,
decision ledger, and doc_memory. Stored in the org document.

Signal Detection: weekly scan comparing state against benchmarks and lens patterns.
Root Cause Walker: causal tree traversal from symptom to root cause through the function graph.
Opportunity Scanner: pattern-matching business state against knowledge base for untapped moves.

Wires:
  Wire 1 — taxonomy → lenses: function health boosts relevant lens weights
  Wire 2 — signal scan → Decision Brain: weekly brief auto-injected as context
  Wire 3 — root cause walker → Journey engine: background causal tree on symptom mention
  Wire 4 — learning loop: signal -> cause -> fix -> measure outcome
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from db import orgs_col, members_col, decisions_col, journeys_col
from business_taxonomy import PROBLEM_TAXONOMY, taxonomy_stats

log = logging.getLogger("business_system")

# ---------- the 15-function dependency graph ----------
# Each function lists upstream dependents: "if X is broken, Y suffers"
DEPENDENCY_GRAPH = {
    "vision":       [],
    "strategy":     ["vision"],
    "product":      ["vision", "strategy"],
    "marketing":    ["strategy", "product"],
    "sales":        ["marketing", "product"],
    "finance":      ["sales"],
    "operations":   ["product", "sales", "finance"],
    "hr":           ["strategy"],
    "customer_success": ["sales", "product"],
    "technology":   ["product"],
    "legal":        ["strategy", "finance"],
    "supply_chain": ["operations", "product"],
    "data":         ["sales", "marketing", "product", "operations"],
    "brand":        ["marketing", "product", "customer_success"],
    "partnerships": ["strategy", "sales"],
    "growth":       ["marketing", "sales", "product"],
}

# Upstream-downstream dependency chain for root cause walking
# Build reverse dependency map for root cause walking
UPSTREAM_MAP = {}
for func_, deps in DEPENDENCY_GRAPH.items():
    for dep in deps:
        UPSTREAM_MAP.setdefault(dep, []).append(func_)

DOWNSTREAM_MAP = DEPENDENCY_GRAPH  # alias for clarity

# Human-readable labels for the 16 business functions
FUNCTION_LABELS = {
    "vision": "Vision & Mission",
    "strategy": "Strategy & Positioning",
    "product": "Product & Value Prop",
    "marketing": "Marketing & Demand Gen",
    "sales": "Sales & Conversion",
    "finance": "Finance & Cash Flow",
    "operations": "Operations & Efficiency",
    "hr": "People & Talent",
    "customer_success": "Customer Success & Retention",
    "technology": "Technology & Engineering",
    "legal": "Legal & Compliance",
    "supply_chain": "Supply Chain & Logistics",
    "data": "Data & Analytics",
    "brand": "Brand & Trust",
    "partnerships": "Partnerships & Alliances",
    "growth": "Growth & Expansion",
}

def _failure_modes_for(func: str) -> list[str]:
    """Pull failure modes from the business taxonomy for a given function."""
    fdata = PROBLEM_TAXONOMY.get(func, {})
    modes = []
    for sd in fdata.get("subdomains", {}).values():
        for cap in sd.get("capabilities", {}).values():
            for fm in cap.get("failures", []):
                modes.append(fm["failure"])
    return modes


def _best_book_for(func: str, failure_text: str) -> Optional[str]:
    """Find the definitive book for a specific failure mode."""
    fdata = PROBLEM_TAXONOMY.get(func, {})
    for sd in fdata.get("subdomains", {}).values():
        for cap in sd.get("capabilities", {}).values():
            for fm in cap.get("failures", []):
                if fm["failure"] == failure_text:
                    return fm["book"]
    return None

# ponytail: lazy aliases — DELETE after all callers use _failure_modes_for()
# Lazy failure-mode lookup per business function
FAILURE_MODES = {f: _failure_modes_for(f) for f in PROBLEM_TAXONOMY}

# Strong signals that indicate system-level problems (cross-functional)
# Known cross-functional failure patterns
_SYSTEM_SIGNALS = [
    ("marketing", "sales", "Marketing brings poor-quality leads → Sales can't close"),
    ("engineering", "marketing", "Slow delivery → Missed launches → Customers leave"),
    ("finance", "product", "Budget cut → Quality drops → Brand weakens"),
    ("sales", "product", "Sales overpromises → Product underdelivers → Churn"),
    ("hr", "product", "Wrong hires → Slow velocity → Market window closes"),
    ("operations", "customer_success", "Manual ops → Slow support → Churn"),
    ("strategy", "all", "Unclear strategy → Every team pulls in different directions"),
]


# Timezone-aware current UTC timestamp
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# Part 1: System Model
# ======================================================================

def init_system_model(org: dict) -> dict:
    """Build or rebuild the system model from org state, journey data, and decision ledger."""
    model = {
        "version": (org.get("system_model", {}).get("version", 0) or 0) + 1,
        "last_built": _now().isoformat(),
        "functions": {},
        "cross_function_signals": [],
    }
    for func in FUNCTION_LABELS:
        model["functions"][func] = _assess_function(func, org)
    model["cross_function_signals"] = _detect_system_signals(model["functions"])
    return model


def _assess_function(func: str, org: dict) -> dict:
    """Score a single business function from available data."""
    health = 50  # neutral default
    evidence = []

    ns = (org.get("north_star") or "").lower()
    prios = [p.lower() for p in (org.get("priorities") or [])]
    rules = (org.get("decision_rules") or "").lower()

    # North Star alignment: if the function maps to a strategic priority, bump health
    for prio in prios:
        if func in prio or FUNCTION_LABELS[func].lower() in prio:
            health += 15
            evidence.append("Strategic priority")

    # Decision ledger signals: recent decisions tagged to this function
    try:
        recent = list(decisions_col.find(
            {"org_id": org["id"], "function": func},
            {"_id": 0, "outcome": 1, "alignment_band": 1, "created_at": 1},
        ).sort("created_at", -1).limit(5))
        good = sum(1 for d in recent if d.get("outcome") == "positive" or d.get("alignment_band") == "green")
        if recent:
            health += (good / len(recent)) * 20 - 10
            evidence.append(f"{good}/{len(recent)} recent decisions went well")
    except Exception:
        pass

    # Journey model signals: blockers, tried, fears that mention this function
    try:
        j = journeys_col.find_one({"user_id": org.get("owner_user_id"), "status": "active"},
                                   {"_id": 0, "blocks": 1, "tried": 1, "fears": 1})
        if j:
            concerns = (j.get("blocks") or []) + (j.get("tried") or []) + (j.get("fears") or [])
            matching = [c for c in concerns if func in c.lower() or FUNCTION_LABELS[func].lower() in c.lower()]
            if matching:
                health -= min(len(matching) * 10, 30)
                evidence.append(f"{len(matching)} unresolved concerns")
    except Exception:
        pass

    # Clamp health
    health = max(5, min(95, round(health)))

    threshold = 50
    status = "healthy" if health >= 70 else "warning" if health >= threshold else "at_risk"

    return {
        "health": health,
        "status": status,
        "evidence": evidence,
        "last_assessed": _now().isoformat(),
    }


def _detect_system_signals(functions: dict) -> list[dict]:
    """Check for known cross-function failure patterns."""
    signals = []
    for upstream, downstream, pattern in _SYSTEM_SIGNALS:
        u = functions.get(upstream, {})
        d = functions.get(downstream, {}) if downstream != "all" else {}
        if u.get("status") == "at_risk" and (downstream == "all" or d.get("status") in ("warning", "at_risk")):
            signals.append({
                "upstream": upstream,
                "downstream": downstream,
                "pattern": pattern,
                "severity": "high" if u.get("health", 50) < 30 else "medium",
            })
    return signals


def persist_system_model(org_id: str, model: dict):
    """Write the system model into the org document."""
    orgs_col.update_one(
        {"id": org_id},
        {"$set": {"system_model": model, "system_model_updated_at": _now().isoformat()}},
    )


def get_system_model(org_id: str) -> Optional[dict]:
    """Read the system model from the org document."""
    org = orgs_col.find_one({"id": org_id}, {"_id": 0, "system_model": 1})
    if not org:
        return None
    return org.get("system_model")


# ======================================================================
# Part 2: Signal Detection
# ======================================================================

def run_signal_scan(org_id: str) -> dict:
    """Weekly scan: compare business state against benchmarks and lens patterns.
    Returns a 'Founder Brief' — top shifts this week."""
    org = orgs_col.find_one({"id": org_id})
    if not org:
        return {"error": "org not found"}

    model = get_system_model(org_id) or init_system_model(org)
    functions = model.get("functions", {})

    signals = []
    for func, state in functions.items():
        label = FUNCTION_LABELS.get(func, func)
        if state["status"] == "at_risk":
            signals.append({
                "function": func,
                "label": label,
                "signal": "at_risk",
                "health": state["health"],
                "detail": f"{label} at {state['health']}/100 — {', '.join(state.get('evidence', ['no evidence']))}",
                "failure_modes": FAILURE_MODES.get(func, [])[:3],
            })
        elif state["status"] == "warning":
            signals.append({
                "function": func,
                "label": label,
                "signal": "warning",
                "health": state["health"],
                "detail": f"{label} at {state['health']}/100 — {', '.join(state.get('evidence', ['no evidence']))}",
            })

    # Sort: at_risk first, then by health ascending
    signals.sort(key=lambda s: (0 if s["signal"] == "at_risk" else 1, s["health"]))

    # System-level signals
    system_signals = model.get("cross_function_signals", [])

    # Generate the brief
    top = signals[:5]
    brief_lines = []
    if top:
        brief_lines.append(f"=== Weekly Signal Scan — {_now().strftime('%d %b %Y')} ===")
        for i, s in enumerate(top, 1):
            brief_lines.append(f"\n{i}. {s['detail']}")
            if s.get("failure_modes"):
                brief_lines.append(f"   Possible causes: {'; '.join(s['failure_modes'][:2])}")

        if system_signals:
            brief_lines.append(f"\n=== System-Level Patterns ({len(system_signals)} detected) ===")
            for ss in system_signals[:3]:
                brief_lines.append(f"  - {ss['pattern']} [severity: {ss['severity']}]")

        brief_lines.append("\nComplete: " + _now().isoformat())
    else:
        brief_lines.append("=== Weekly Signal Scan ===")
        brief_lines.append("No significant shifts detected. All functions healthy.")

    result = {
        "scan_time": _now().isoformat(),
        "signals": signals,
        "system_signals": system_signals,
        "brief": "\n".join(brief_lines),
        "total_functions": len(functions),
        "at_risk_count": sum(1 for f in functions.values() if f["status"] == "at_risk"),
        "warning_count": sum(1 for f in functions.values() if f["status"] == "warning"),
        "healthy_count": sum(1 for f in functions.values() if f["status"] == "healthy"),
    }
    # Wire 4: persist scan for trend analysis
    try:
        record_signal_scan(org_id, result)
    except Exception:
        pass
    return result


# ======================================================================
# Part 3: Root Cause Walker
# ======================================================================

def walk_root_cause(org_id: str, symptom_func: str, max_depth: int = 3) -> dict:
    """Walk the dependency graph from a symptom function to find root causes.
    symptom_func: the function showing the problem (e.g., 'sales', 'revenue' mapped to 'sales')
    """
    func_map = {v.lower().split("&")[0].strip(): k for k, v in FUNCTION_LABELS.items()}
    func = symptom_func.lower().strip()
    func = func_map.get(func, func)
    if func not in FUNCTION_LABELS:
        return {"error": f"Unknown function: {symptom_func}", "known": list(FUNCTION_LABELS.keys())}

    # Normalize revenue → sales, churn → customer_success
    aliases = {"revenue": "sales", "churn": "customer_success",
               "engineering": "technology", "dev": "technology",
               "hiring": "hr", "talent": "hr", "support": "customer_success",
               "marketing_spend": "marketing", "cash": "finance",
               "runway": "finance", "pricing": "finance",
               "branding": "brand", "trust": "brand",
               "competition": "strategy", "positioning": "strategy",
               "growth_rate": "growth", "acquisition": "growth",
               "retention": "customer_success", "cac": "marketing",
               "ltv": "customer_success", "velocity": "technology",
               "culture": "hr", "burnout": "hr",
               "logistics": "supply_chain", "inventory": "supply_chain",
               "analytics": "data", "metrics": "data",
               "compliance": "legal", "patents": "legal", "ip": "legal",
               "alliances": "partnerships", "channels": "partnerships",
               "mission": "vision", "purpose": "vision"}
    func = aliases.get(func, func)
    if func not in FUNCTION_LABELS:
        return {"error": f"Unknown function after alias resolution: {symptom_func}"}

    org = orgs_col.find_one({"id": org_id})
    model = get_system_model(org_id) or (init_system_model(org) if org else None)
    if not model:
        return {"error": "No system model — run init first"}

    functions = model.get("functions", {})

    tree = _build_causal_tree(func, functions, visited=set(), depth=0, max_depth=max_depth)
    return {
        "symptom": symptom_func,
        "root_function": func,
        "root_label": FUNCTION_LABELS[func],
        "causal_tree": tree,
        "analyzed_at": _now().isoformat(),
    }


def _build_causal_tree(func: str, functions: dict, visited: set, depth: int, max_depth: int) -> dict:
    """Recursively build a causal tree from a function through its upstream dependencies."""
    if func in visited or depth > max_depth:
        return {"function": func, "label": FUNCTION_LABELS.get(func, func),
                "depth": depth, "truncated": True}
    visited.add(func)

    state = functions.get(func, {})
    health = state.get("health", 50)
    status = state.get("status", "unknown")

    children = []
    upstream = DEPENDENCY_GRAPH.get(func, [])
    for u_func in upstream:
        u_state = functions.get(u_func, {})
        u_health = u_state.get("health", 50)
        # Only descend into upstream functions that are worse or equal health
        if u_health <= health or u_state.get("status") in ("warning", "at_risk"):
            children.append(_build_causal_tree(u_func, functions, visited.copy(), depth + 1, max_depth))

    failure_modes = FAILURE_MODES.get(func, [])[:4]

    return {
        "function": func,
        "label": FUNCTION_LABELS.get(func, func),
        "health": health,
        "status": status,
        "depth": depth,
        "failure_modes": failure_modes,
        "upstream": [DEPENDENCY_GRAPH.get(func, [])],
        "downstream": [UPSTREAM_MAP.get(func, [])],
        "children": children,
    }


# ======================================================================
# Part 4: Opportunity Scanner
# ======================================================================

# Opportunity patterns derived from the 100-book knowledge base
OPPORTUNITY_PATTERNS = {
    "product": [
        {"pattern": "Adjacent market: what's the natural next segment after your current users?",
         "source": "Crossing the Chasm, Blue Ocean Strategy"},
        {"pattern": "Product extension: which feature do power users hack together themselves?",
         "source": "The Mom Test, Competing Against Luck"},
        {"pattern": "Platform play: can your product become the infrastructure others build on?",
         "source": "7 Powers, Zero to One"},
    ],
    "marketing": [
        {"pattern": "Under-served channel: where do your customers already hang out that competitors ignore?",
         "source": "Traction, Purple Cow"},
        {"pattern": "Story gap: what belief about your category is widely held but wrong?",
         "source": "Building a StoryBrand, Made to Stick"},
        {"pattern": "Earned attention: what can you do that's so remarkable people talk about it unprompted?",
         "source": "Contagious, Purple Cow, The Tipping Point"},
    ],
    "sales": [
        {"pattern": "Up-sell path: what do your best customers naturally need next?",
         "source": "SPIN Selling, How Brands Grow"},
        {"pattern": "Partnership distribution: who already has your customer and isn't competing?",
         "source": "Traction, Business Model Generation"},
    ],
    "strategy": [
        {"pattern": "Strategic inflection point: is a technology/market shift creating a new game where you have an advantage?",
         "source": "7 Powers, The Innovator's Dilemma"},
        {"pattern": "Unbundling opportunity: which part of an incumbent's bundle can you do 10x better?",
         "source": "Business Model Generation, Zero to One"},
        {"pattern": "Counter-positioning: can you adopt a model the incumbent can't copy without hurting themselves?",
         "source": "7 Powers, Good Strategy Bad Strategy"},
    ],
}


def scan_opportunities(org_id: str) -> dict:
    """Find untapped opportunities based on the current business state."""
    org = orgs_col.find_one({"id": org_id})
    if not org:
        return {"error": "org not found"}

    model = get_system_model(org_id) or init_system_model(org)
    functions = model.get("functions", {})

    opportunities = []
    for func, patterns in OPPORTUNITY_PATTERNS.items():
        state = functions.get(func, {})
        if state.get("status") == "healthy":
            opportunities.append({
                "function": func,
                "label": FUNCTION_LABELS[func],
                "health": state["health"],
                "match": "strong_position",
                "suggestions": patterns,
            })
        elif state.get("status") == "warning":
            opportunities.append({
                "function": func,
                "label": FUNCTION_LABELS[func],
                "health": state["health"],
                "match": "gap_to_fill",
                "suggestions": patterns[:1],
            })

    # Look for adjacent expansion: adjacent functions where one is healthy and the other isn't
    adjacent_opps = []
    for func, deps in DEPENDENCY_GRAPH.items():
        if functions.get(func, {}).get("status") == "healthy":
            for dep in deps:
                if functions.get(dep, {}).get("status") in ("warning", "at_risk"):
                    adjacent_opps.append({
                        "source": FUNCTION_LABELS.get(func, func),
                        "target": FUNCTION_LABELS.get(dep, dep),
                        "pattern": f"Leverage your strength in {FUNCTION_LABELS.get(func, func)} to fix {FUNCTION_LABELS.get(dep, dep)}",
                    })

    return {
        "scan_time": _now().isoformat(),
        "opportunities": opportunities,
        "adjacent_leverage": adjacent_opps[:5],
        "summary": f"Found {len(opportunities)} opportunity areas and {len(adjacent_opps)} adjacent leverage points.",
    }


# ======================================================================
# Wire 3: Symptom detection → root cause injection for engine/journey
# ======================================================================

# Symptom keywords mapped to business functions
_SYMPTOM_PATTERNS = [
    (r'\b(revenue|sales).*(dropping|declining|falling|down|decreasing|flat|stalled|slow)|(dropping|declining|falling).*(revenue|sales)', 'sales'),
    (r'\b(churn|cancelled|leaving|quitting|customer.*los)', 'customer_success'),
    (r'\b(not selling|no traction|product.*market.*fit.*not|no.*pmf)\b', 'product'),
    (r'\b(engineering.*slow|velocity.*problem|deploy.*slow|release.*slow|tech.*debt)\b', 'technology'),
    (r'\b(running out of money|cash.*running|runway.*problem|out of cash|burn.*rate.*high)\b', 'finance'),
    (r'\b(can.?t.*(hire|find|recruit)|hiring.*(can.?t|problem|hard)|talent.*(shortage|problem))\b', 'hr'),
    (r'\b(marketing.*(not working|fail|broken)|campaign.*fail|leads.*(dry|dead|none)|demand.*(dead|none))\b', 'marketing'),
    (r'\b(growth.*(stalled|plateau|flat|none|slow|stopped)|(hit|reached).*ceiling|not.*growing)\b', 'growth'),
    (r'\b(competitor|competition|undercut|losing to|losing deals|market.*share.*los)\b', 'strategy'),
    (r'\b(ops.*broken|process.*broken|bottleneck|always.*(behind|late)|efficiency.*problem)\b', 'operations'),
    (r'\b(brand.*problem|trust.*issue|reputation.*damag|bad.*press|negative.*review)\b', 'brand'),
    (r'\b(data.*wrong|wrong.*number|dashboard.*broken|data.*broken|bad.*metric)\b', 'data'),
    (r'\b(partnership.*(sour|fail|problem|broke)|partner.*(problem|fail)|alliance.*(broke|fail))\b', 'partnerships'),
    (r'\b(founder.*(burnout|burnt|overwhelm|stressed|can.?t.*do.*this))\b', 'leadership'),
    (r'\b(team.*conflict|co.?founder.*(fight|problem|conflict)|everyone.*leaving|morale.*(low|problem))\b', 'leadership'),
]


def detect_symptoms(user_message: str) -> list[str]:
    """Scan a user message for business symptom keywords. Returns list of affected function names."""
    detected = []
    msg_lower = user_message.lower()
    for pattern, func in _SYMPTOM_PATTERNS:
        import re
        if re.search(pattern, msg_lower):
            if func not in detected:
                detected.append(func)
    return detected[:3]  # max 3 functions to avoid context bloat


def root_cause_context_block(org_id: str, user_message: str) -> str:
    """Wire 3: detect symptoms in user message, walk root cause tree, return context block.
    Pure text injection for engine/journey prompts. Empty string if no symptoms detected."""
    symptoms = detect_symptoms(user_message)
    if not symptoms:
        return ""
    parts = []
    for func in symptoms[:2]:  # max 2 walks to control token cost
        walk = walk_root_cause(org_id, func, max_depth=2)
        if walk.get("error"):
            continue
        tree = walk.get("causal_tree", {})
        parts.append(_format_walk_for_prompt(tree))
    if not parts:
        return ""
    return (
        "ROOT CAUSE ANALYSIS (auto-detected from the founder's message — reference this ANALYSIS, "
        "not the detection process):\n" + "\n\n".join(parts)
    )


def _format_walk_for_prompt(node, indent=0):
    """Format a causal tree node into a compact text line for the LLM prompt."""
    parts = [f"{'  ' * indent}{node.get('label', node.get('function', ''))} "
             f"(health: {node.get('health', '?')}/100, {node.get('status', '?')})"]
    if node.get('failure_modes'):
        parts.append(f"{'  ' * (indent+1)}Common failures: {'; '.join(node['failure_modes'][:3])}")
    for child in node.get('children', []):
        parts.append(_format_walk_for_prompt(child, indent + 1))
    return "\n".join(parts)


# ======================================================================
# Wire 4: Learning loop — store outcomes for trend analysis
# ======================================================================

def record_signal_scan(org_id: str, scan_result: dict):
    """Store the signal scan result in the org's system_model for trend analysis.
    Keeps the last 12 weeks of scans."""
    scan_entry = {
        "time": scan_result.get("scan_time", ""),
        "brief": scan_result.get("brief", ""),
        "at_risk_count": scan_result.get("at_risk_count", 0),
        "warning_count": scan_result.get("warning_count", 0),
        "signals": [s.get("function") for s in scan_result.get("signals", []) if s.get("signal") == "at_risk"][:5],
    }
    orgs_col.update_one(
        {"id": org_id},
        {
            "$set": {"system_model.last_scan_brief": scan_entry["brief"]},
            "$push": {
                "system_model.scan_history": {
                    "$each": [scan_entry],
                    "$slice": -12,  # ponytail: rolling 12-week window, enough for trend detection
                }
            },
        },
    )


def trend_analysis(org_id: str) -> str:
    """Analyze scan history for trends: improving, worsening, or holding steady per function."""
    org = orgs_col.find_one({"id": org_id}, {"_id": 0, "system_model.scan_history": 1})
    if not org:
        return ""
    history = org.get("system_model", {}).get("scan_history", [])
    if len(history) < 2:
        return ""
    lines = ["WEEKLY TREND ANALYSIS:"]
    for func in FUNCTION_LABELS:
        counts = [1 for h in history if func in h.get("signals", [])]
        recent = sum(counts[-4:])  # last 4 weeks
        older = sum(counts[:-4])   # weeks before
        if recent > older + 1:
            lines.append(f"  - {FUNCTION_LABELS[func]}: WORSENING ({recent} flags recent vs {older} prior)")
        elif older > recent + 1:
            lines.append(f"  - {FUNCTION_LABELS[func]}: IMPROVING ({recent} flags recent vs {older} prior)")
    return "\n".join(lines) if len(lines) > 1 else ""


# ======================================================================
# Demo / self-check
# ======================================================================
if __name__ == "__main__":
    # Unit-level assertions for core logic
    assert len(FUNCTION_LABELS) == 16
    assert len(DEPENDENCY_GRAPH) == 16
    assert all(f in FUNCTION_LABELS for f in DEPENDENCY_GRAPH)

    # Graph integrity: every upstream dependency must be a known function
    for func, deps in DEPENDENCY_GRAPH.items():
        for dep in deps:
            assert dep in FUNCTION_LABELS, f"{func} depends on unknown {dep}"

    # Alias map: all values must resolve to real functions
    aliases = {
        "revenue": "sales", "churn": "customer_success",
        "engineering": "technology", "dev": "technology",
        "hiring": "hr", "talent": "hr", "support": "customer_success",
        "marketing_spend": "marketing", "cash": "finance",
        "pricing": "finance", "branding": "brand", "trust": "brand",
        "competition": "strategy", "positioning": "strategy",
        "growth_rate": "growth", "acquisition": "growth",
        "retention": "customer_success", "cac": "marketing",
        "ltv": "customer_success", "velocity": "technology",
        "culture": "hr", "burnout": "hr",
        "logistics": "supply_chain", "inventory": "supply_chain",
        "analytics": "data", "metrics": "data",
        "compliance": "legal", "patents": "legal", "ip": "legal",
        "alliances": "partnerships", "channels": "partnerships",
        "mission": "vision", "purpose": "vision",
    }
    for alias, target in aliases.items():
        assert target in FUNCTION_LABELS, f"Alias {alias} → unknown {target}"

    print("OK — all assertions passed")
