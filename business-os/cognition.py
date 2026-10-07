"""Cognition Core — context-aware decision intelligence for SmartDecigen.

The moat is not the prompt; it is WHAT GOES INTO the prompt. This module assembles,
at runtime and at zero LLM cost, the layers that turn a generic LLM into a mentor
who knows THIS founder:

  L1 identity  — name, dream, capacity, unfair advantage (from the questionnaire)
  L5 memory    — this founder's past relevant decisions and their real outcomes
  L6 algorithm — the per-decision-category reasoning checklist
  L4 lenses    — the 3 most relevant book-derived reasoning modules (lenses.py)

classify_decision() is a pure keyword router into 9 founder decision categories.
cognition_block() returns one string ready to inject into any engine prompt.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from db import users_col, decisions_col, journeys_col, members_col, orgs_col, telemetry_col
from lenses import select_lenses

log = logging.getLogger("cognition")

# --------------------------------------------------------------- decision-type router
# category -> (trigger keywords, preferred lens ids, reasoning algorithm)
CATEGORIES = {
    "deal_negotiation": {
        "kw": ["distributor", "deal", "offer from", "contract", "terms", "exclusiv", "negotiat", "vendor",
               "supplier", "partnership", "agreement", "mou", "franchise", "counter offer", "listing fee",
               "wants 3", "wants 4", "margin they", "their offer"],
        "lenses": ["munger_incentives", "taleb_antifragile", "voss_negotiation", "thorndike_capital", "lafley_wwhtt",
                     "art_of_war", "art_of_strategy", "how_to_win_friends", "adams_persuasion"],
        "algo": ("DEAL/NEGOTIATION ALGORITHM: 1) Trace the counterparty's incentives: what do they gain, where "
                 "do interests diverge? 2) Price the optionality being traded: what flexibility does this deal "
                 "sell, is the payment worth years of it, can a pilot keep the option alive? 3) What would have "
                 "to be true for this deal to be right, and what is the cheapest test of the shakiest condition? "
                 "4) Restate the deal as three numbers: cash out date, cash back date, certainty. 5) Negotiation "
                 "posture: label their position, ask calibrated How/What questions, never split the difference, "
                 "trade non-monetary terms."),
    },
    "people_team": {
        "kw": ["hire", "hiring", "fire ", "firing", "cofounder", "co-founder", "employee", "team member",
               "cto", "salary", "quit", "resign", "underperform", "delegate", "first hire", "intern",
               "agency or in-house", "freelancer"],
        "lenses": ["grove_leverage", "horowitz_struggle", "dalio_principles", "bungay_action", "coyle_culture",
                     "seven_habits", "effective_executive", "team_of_teams", "turn_the_ship_around", "e_myth_revisited",
                     "how_to_win_friends", "start_with_why", "delivering_happiness", "creativity_inc", "reinventing_organizations",
                     "berdee_psychopaths", "greene_human_nature", "kishimi_courage"],
        "algo": ("PEOPLE/TEAM ALGORITHM: 1) Wartime or peacetime? Survival pressure changes the right call. "
                 "2) Person or machine: is this individual failing, or is the design (role, incentives, "
                 "information) producing the failure? 3) Task-relevant maturity: does their freedom match their "
                 "experience at THIS task? 4) Hire for the spike this stage needs, not absence of weakness. "
                 "5) For delegation: give intent (outcome + why + constraints) and demand a back-brief. "
                 "6) Check the culture signals: safety, vulnerability, purpose."),
    },
    "growth_marketing": {
        "kw": ["grow", "customers", "marketing", "ads", "instagram", "sales dropped", "channel", "traffic",
               "leads", "awareness", "brand", "followers", "reach", "promotion", "campaign", "word of mouth",
               "referral"],
        "lenses": ["weinberg_traction", "sharp_growth", "ries_positioning", "berger_contagious", "cialdini_influence",
                    "purple_cow", "this_is_marketing", "tipping_point", "made_to_stick", "pre_suasion", "immutable_laws", "hooked"],
        "algo": ("GROWTH/MARKETING ALGORITHM: 1) Penetration math first: does this reach NEW and light buyers, "
                 "or re-touch existing fans? 2) Channel discipline: test few channels cheaply with real numbers, "
                 "then concentrate on the one that works; hunt the underpriced channel others ignore. 3) Position "
                 "check: what one word or slot do they own, in whose mind? 4) Message check: concrete, internal "
                 "problem named, grunt-test clear. 5) Count results: every campaign carries a counted action."),
    },
    "pricing_offer": {
        "kw": ["price", "pricing", "discount", "premium", "charge", "subscription", "pack", "offer", "rate card",
               "underpricing", "raise prices", "mrp", "margin on"],
        "lenses": ["sutherland_alchemy", "cialdini_influence", "helmer_power", "meadows_systems",
                    "personal_mba", "business_model_generation"],
        "algo": ("PRICING/OFFER ALGORITHM: 1) Perceived value is real value: what signals (name, packaging, "
                 "story, ritual) justify the price before touching the number? 2) Choose the door: structurally "
                 "cheaper or provably worth more; the middle loses to both. 3) Second-order check: what does this "
                 "discount TEACH customers to expect? Shifting the burden onto discounts atrophies the brand. "
                 "4) Loss-framed true scarcity only; fake urgency destroys trust. 5) Anchor high with a premium "
                 "option; precise odd numbers read as calculated, round numbers as negotiable."),
    },
    "product_validation": {
        "kw": ["product idea", "feature", "mvp", "launch", "validate", "prototype", "build a", "new product",
               "feedback from customers", "beta", "app idea", "would they buy", "customer interview"],
        "lenses": ["fitzpatrick_momtest", "christensen_jtbd", "ries_leanstartup", "heath_wrap",
                    "the_right_it", "innovators_solution", "sprint", "range", "super_thinking"],
        "algo": ("PRODUCT/VALIDATION ALGORITHM: 1) The Mom Test: collect past behavior and commitments, never "
                 "opinions about the idea; compliments are not data. 2) Find the job-to-be-done: what progress "
                 "is the customer hiring this for, in what circumstance, firing what? 3) Name the riskiest "
                 "assumption and design the smallest real-behavior experiment that tests it. 4) Define kill "
                 "criteria before building. 5) Shipped is not learned: measure cohort behavior, not applause."),
    },
    "crisis_survival": {
        "kw": ["runway", "cash crisis", "can't pay", "cannot pay", "losing money", "shut down", "survive",
               "emergency", "debt", "loan due", "salaries due", "out of money", "3 months left", "burn"],
        "lenses": ["horowitz_struggle", "taleb_swan", "rumelt_kernel", "bevelin_wisdom",
                     "skin_in_the_game", "mans_search_for_meaning", "shoe_dog", "the_dip",
                     "berdee_psychopaths", "kishimi_courage"],
        "algo": ("CRISIS/SURVIVAL ALGORITHM: 1) Wartime rules: exactly one priority; strip every peacetime "
                 "initiative. 2) Sacred-runway math: what cash is untouchable, what is the honest date, which "
                 "single dependency's failure is fatal? 3) The kernel: name the ONE critical obstacle between "
                 "here and safety; ignore everything else. 4) For each urgent-feeling move, run the do-nothing "
                 "test: what actually happens if we wait two weeks? 5) Normalize the Struggle, then produce the "
                 "next 48-hour move; hope lives in moves."),
    },
    "strategy_direction": {
        "kw": ["strategy", "direction", "pivot", "focus on what", "vision", "long term", "which market",
               "expand", "where to play", "next year plan", "diversify", "new city", "second location"],
        "lenses": ["rumelt_kernel", "helmer_power", "lafley_wwhtt", "moore_chasm", "kim_blueocean",
                    "competitive_strategy", "good_to_great", "zero_to_one", "innovators_dilemma", "measure_what_matters",
                    "business_model_generation", "your_strategy_needs_strategy", "the_halo_effect",
                    "infinite_game", "start_with_why"],
        "algo": ("STRATEGY/DIRECTION ALGORITHM: 1) Build the kernel: diagnosis of the critical obstacle, a "
                 "guiding policy that rules options OUT, 2-3 coherent actions. 2) Where to play: which single "
                 "field can they WIN in 6-12 months, and who is deliberately not served? 3) Power check: which "
                 "durable advantage (benefit + barrier) does this path build, and is its window open at their "
                 "stage? 4) Convert the grand goal into the nearest proximate objective. 5) Beachhead before "
                 "ocean: dominate one narrow segment completely before adjacency."),
    },
    "money_allocation": {
        "kw": ["invest", "spend on", "budget", "surplus", "profit this", "savings", "allocate", "buy equipment",
               "capex", "extra cash", "where should the money", "reinvest"],
        "lenses": ["thorndike_capital", "taleb_antifragile", "munger_incentives",
                    "intelligent_investor", "most_important_thing", "warren_buffett_way",
                    "personal_mba", "compound_effect"],
        "algo": ("CAPITAL ALLOCATION ALGORITHM: 1) Surplus is a decision: enumerate the uses (product, growth, "
                 "debt, buffer, new bets) and compare expected returns explicitly. 2) Compare against the best "
                 "alternative, never against doing nothing. 3) Barbell the risk: sacred core, small capped "
                 "experiments, nothing medium. 4) Three numbers per option: cash out date, cash back date, "
                 "certainty. 5) Denominator check: does this grow value per founder-hour and per rupee of risk, "
                 "or just size?"),
    },
    "ops_execution": {
        "kw": ["process", "operations", "inventory", "delivery", "quality issue", "bottleneck", "time management",
               "productivity", "overwhelmed with work", "systems", "sop", "automation", "supply"],
        "lenses": ["grove_leverage", "meadows_systems", "flyvbjerg_bigthings",
                    "essentialism", "deep_work", "getting_things_done", "pareto_principle",
                    "four_disciplines_execution", "the_one_thing", "execution", "first_things_first",
                    "e_myth_revisited", "four_hour_workweek", "compound_effect", "rework", "indistractable"],
        "algo": ("OPS/EXECUTION ALGORITHM: 1) Find the limiting step: map the stages, locate the constraint, "
                 "refuse to optimize anything else. 2) Structure over blame: recurring failures indict the "
                 "design (incentives, information, delays), not the people. 3) Fix problems at the lowest-value "
                 "stage. 4) Pair every quantity metric with its quality shadow. 5) For big builds: reference-"
                 "class the estimate, pilot the storyboard version, modularize so unit two learns from unit one."),
    },
}


def classify_decision(text: str) -> Optional[str]:
    """Pure keyword router. Returns category id or None (generic)."""
    hay = (text or "").lower()
    best, best_score = None, 0
    for cat, spec in CATEGORIES.items():
        s = sum(1 for kw in spec["kw"] if kw in hay)
        if s > best_score:
            best, best_score = cat, s
    return best if best_score >= 1 else None


# --------------------------------------------------------------- L1 founder identity
def identity_block(user: dict) -> str:
    """Who this founder is — makes the engine a mentor who KNOWS them, not a fresh consultant.
    Built from the signup name + the 4-question questionnaire (dream/capacity/advantage/potential)."""
    if not user:
        return ""
    fresh = users_col.find_one({"id": user["id"]}, {"_id": 0, "name": 1, "questionnaire": 1}) or {}
    name = (fresh.get("name") or user.get("name") or "").strip()
    q = fresh.get("questionnaire") or {}
    parts = []
    if name:
        parts.append(f"- Name: {name}")
    if (q.get("dream") or "").strip():
        parts.append(f"- Their dream (their own words): {q['dream'].strip()[:400]}")
    if (q.get("capacity") or "").strip():
        parts.append(f"- Their capacity and constraints: {q['capacity'].strip()[:400]}")
    if (q.get("advantage") or "").strip():
        parts.append(f"- Their unfair advantage: {q['advantage'].strip()[:400]}")
    if (q.get("potential") or "").strip():
        parts.append(f"- What success would mean to them: {q['potential'].strip()[:400]}")
    if not parts:
        return ""
    return (
        "THE FOUNDER YOU ARE TALKING TO (you have worked with them before; sound like a mentor who knows them: "
        "use their first name naturally but sparingly, connect advice to their stated dream and constraints, "
        "and never recite this data back as a list):\n" + "\n".join(parts)
    )


# --------------------------------------------------------------- L5 past-decision memory
def past_decisions_block(user_id: str, text: str, category: Optional[str], limit: int = 3) -> str:
    """This founder's most relevant past decisions + real outcomes. Relevance = shared keywords
    with the current question; falls back to recency. Zero LLM, one indexed query."""
    try:
        rows = list(decisions_col.find(
            {"user_id": user_id},
            {"_id": 0, "question": 1, "key_takeaway": 1, "committed_action": 1, "status": 1,
             "outcome": 1, "impact_inr": 1, "created_at": 1},
        ).sort("created_at", -1).limit(25))
    except Exception as e:
        log.warning(f"past_decisions lookup failed: {e}")
        return ""
    if not rows:
        return ""
    words = {w for w in (text or "").lower().split() if len(w) > 4}

    def rel(r):
        qwords = set((r.get("question") or "").lower().split())
        return len(words & qwords)

    rows.sort(key=lambda r: (-rel(r),))
    chosen = [r for r in rows if rel(r) > 0][:limit] or rows[:1]
    lines = []
    for r in chosen:
        q = (r.get("question") or "")[:220]
        tk = (r.get("key_takeaway") or "")[:220]
        line = f"- They asked: {q}\n  You advised: {tk}"
        if (r.get("committed_action") or "").strip():
            line += f"\n  They committed: {str(r['committed_action'])[:200]}"
        oc = r.get("outcome") or {}
        if isinstance(oc, dict) and oc.get("status"):
            imp = r.get("impact_inr")
            line += f"\n  Real outcome: {oc.get('status')}" + (f", impact about Rs {imp}" if imp else "")
        lines.append(line)
    return (
        "YOUR SHARED HISTORY WITH THIS FOUNDER (real past decisions; build on them, never re-suggest what "
        "failed, and when today's situation rhymes with one of these, say so explicitly):\n" + "\n".join(lines)
    )


# --------------------------------------------------------------- L2 company state (journey model digest)
def company_state_block(user_id: str) -> str:
    """Compact digest of THIS USER'S OWN journey situation model, so the Brain answers
    runway-aware and situation-aware without the founder retyping their business.
    Self-data only (journeys are per-user), so there is no cross-user leakage risk.
    Kept lean: ~300 tokens max, empty string when no journey exists."""
    try:
        j = journeys_col.find_one(
            {"user_id": user_id},
            {"_id": 0, "objective": 1, "model": 1, "confidence": 1, "hypotheses": 1,
             "direction": 1, "milestones": 1})
    except Exception as e:
        log.warning(f"company_state lookup failed: {e}")
        return ""
    if not j or not (j.get("objective") or "").strip():
        return ""
    m = j.get("model") or {}

    def _join(v, cap=4):
        if isinstance(v, list):
            return "; ".join(str(x) for x in v[:cap])
        if isinstance(v, dict):
            return "; ".join(f"{k}: {val}" for k, val in list(v.items())[:cap])
        return str(v or "")

    lines = [f"- Their goal: {str(j['objective'])[:250]}"]
    for key, label in (("why_now", "Why now"), ("constraints", "Hard constraints"),
                       ("blockers", "Blockers"), ("leverage", "Leverage points"),
                       ("resources", "Resources"), ("timeline", "Timeline")):
        v = _join(m.get(key))
        if v.strip():
            lines.append(f"- {label}: {v[:300]}")
    hyps = [h for h in (j.get("hypotheses") or []) if isinstance(h, dict) and h.get("status") != "ruled_out"]
    if hyps:
        top = max(hyps, key=lambda h: h.get("probability", 0))
        if top.get("statement"):
            lines.append(f"- Current leading path hypothesis ({top.get('probability', 0)}%): {str(top['statement'])[:200]}")
    d = j.get("direction") or {}
    if isinstance(d, dict) and (d.get("decision") or "").strip():
        lines.append(f"- Agreed direction: {str(d['decision'])[:250]}")
    ms = [x for x in (j.get("milestones") or []) if isinstance(x, dict)]
    if ms:
        open_ms = [x.get("title", "") for x in ms if x.get("status") not in ("done", "dropped")][:3]
        if open_ms:
            lines.append(f"- Open milestones: {'; '.join(str(t)[:80] for t in open_ms)}")
    return (
        "THIS FOUNDER'S LIVE BUSINESS STATE (from your ongoing deep conversation with them; treat these facts "
        "as known, do NOT re-ask for them, and check every recommendation against these constraints):\n"
        + "\n".join(lines)
    )


# --------------------------------------------------------------- L3 founder operating codex
def codex_block(user: dict) -> str:
    """Compact founder operating codex from the founder_profile on the org.
    Tells the engine HOW to work with this person (personality, style, blind spots),
    not just WHO they are. Silently adapts tone and framing.
    Returns empty string when no profile exists."""
    if not user:
        return ""
    try:
        m = members_col.find_one({"user_id": user["id"], "status": "active", "role": "owner"})
        if not m:
            return ""
        org = orgs_col.find_one({"id": m["org_id"]}, {"_id": 0, "founder_profile": 1})
    except Exception:
        return ""
    if not org:
        return ""
    p = org.get("founder_profile") or {}
    if not isinstance(p, dict):
        return ""
    summary = (p.get("summary") or "").strip()
    if not summary:
        return ""
    lines = [f"- Operator summary: {summary}"]
    for key, label in (
        ("personality", "Personality"),
        ("working_style", "Working style"),
        ("communication_style", "Communication style"),
        ("decision_style", "Decision style"),
        ("risk_appetite", "Risk appetite"),
        ("strengths", "Strengths"),
        ("blind_spots", "Watch for"),
        ("motivations", "Motivations"),
    ):
        val = (p.get(key) or "").strip()
        if val:
            lines.append(f"- {label}: {val}")
    return (
        "FOUNDER CODEX — how to work with THIS person (silently adapt your tone, framing, "
        "and recommendations to fit their operating style; never quote this back at them):\n"
        + "\n".join(lines)
    )


# --------------------------------------------------------------- Ch.11: Decision DNA
def decision_dna_block(user_id: str) -> str:
    """Inferred decision algorithm from observed behavior. Pure computation, zero LLM.
    Models HOW the founder decides: speed, risk, phase preferences, decision types."""
    try:
        decisions = list(decisions_col.find(
            {"user_id": user_id},
            {"_id": 0, "mode": 1, "status": 1, "committed_action": 1, "created_at": 1,
             "predicted_outcome": 1, "outcome": 1},
        ).sort("created_at", -1).limit(50))
        turns = list(telemetry_col.find(
            {"user_id": user_id, "type": "discussion_turn"},
            {"_id": 0, "at": 1},
        ).sort("at", -1).limit(50))
    except Exception as e:
        log.warning(f"decision_dna lookup failed: {e}")
        return ""

    n = len(decisions)
    if n < 3:
        return ""  # not enough data

    # Decision speed: average days between turns
    def _aware(dt):
        if not isinstance(dt, datetime):
            return datetime.min.replace(tzinfo=timezone.utc)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    speed = "medium"
    if len(turns) >= 4:
        sorted_turns = sorted(turns, key=lambda x: _aware(x.get("at")))
        gaps = []
        for i in range(1, len(sorted_turns)):
            a = sorted_turns[i-1].get("at")
            b = sorted_turns[i].get("at")
            if a and b:
                gaps.append((_aware(b) - _aware(a)).total_seconds() / 3600)
        if gaps:
            avg_hours = sum(gaps) / len(gaps)
            speed = "fast" if avg_hours < 48 else ("slow" if avg_hours > 168 else "medium")

    # Risk appetite: inferred from commitment rate and outcome success
    committed = sum(1 for d in decisions if d.get("committed_action"))
    commit_rate = committed / n if n else 0
    outcomes = [d for d in decisions if (d.get("outcome") or {}).get("status") in ("success", "partial", "failed")]
    success_rate = sum(1 for d in outcomes if d["outcome"]["status"] == "success") / len(outcomes) if outcomes else 0.5
    risk = "high" if commit_rate > 0.7 and success_rate > 0.6 else ("low" if commit_rate < 0.3 else "medium")

    # Preferred decision modes
    modes = {}
    for d in decisions:
        m = d.get("mode", "answer")
        modes[m] = modes.get(m, 0) + 1
    preferred_mode = max(modes, key=modes.get) if modes else "answer"

    # Calibration: average predicted confidence vs actual success
    predicted = [d for d in decisions if (d.get("predicted_outcome") or {}).get("confidence")]
    avg_pred_conf = round(sum(d["predicted_outcome"]["confidence"] for d in predicted) / len(predicted)) if predicted else None
    calibration_note = ""
    if avg_pred_conf is not None and outcomes:
        actual_rate = round(100 * success_rate)
        gap = avg_pred_conf - actual_rate
        calibration_note = (f"Overconfident by {gap}%" if gap > 10
                      else f"Underconfident by {-gap}%" if gap < -10
                      else "Well-calibrated")

    lines = [
        f"DECISION DNA (inferred from {n} past decisions — HOW they decide, not just what):",
        f"- Decision speed: {speed} (avg hours between turns)",
        f"- Risk posture: {risk} (commitment rate {round(commit_rate*100)}%, outcome success {round(success_rate*100)}%)",
        f"- Preferred mode: {preferred_mode}",
    ]
    if calibration_note:
        lines.append(f"- Calibration: {calibration_note} (predict {avg_pred_conf}% confident, actual {round(success_rate*100)}%)")
    lines.append("Silently fit your recommendations to this decision style. Never quote the DNA back at them.")
    return "\n".join(lines)


# --------------------------------------------------------------- assembled block
def cognition_block(user: dict, text: str, model: Optional[dict] = None,
                    include_identity: bool = True, include_memory: bool = True,
                    include_company_state: bool = False,
                    include_codex: bool = False,
                    include_dna: bool = False,
                    function_health: Optional[dict] = None) -> str:
    """One string with every cognition layer that applies to this turn. Lean by design:
    empty sections are omitted entirely so quiet turns stay cheap."""
    category = classify_decision(text)
    spec = CATEGORIES.get(category) if category else None
    sections = []
    if include_identity:
        ib = identity_block(user)
        if ib:
            sections.append(ib)
    if include_codex and user:
        cx = codex_block(user)
        if cx:
            sections.append(cx)
    if include_dna and user:
        dna = decision_dna_block(user["id"])  # Ch.11: Decision DNA
        if dna:
            sections.append(dna)
    if include_company_state and user:
        cs = company_state_block(user["id"])
        if cs:
            sections.append(cs)
    if include_memory and user:
        pb = past_decisions_block(user["id"], text, category)
        if pb:
            sections.append(pb)
    if spec:
        sections.append("DECISION TYPE DETECTED: " + category.replace("_", " ").upper() + "\n" + spec["algo"])
    lens_block = select_lenses(text, model, boost_ids=(spec["lenses"] if spec else None),
                               function_health=function_health)
    if lens_block:
        sections.append(lens_block)
    if sections:
        log.info(f"cognition: category={category} sections={len(sections)}")
    return "\n\n".join(sections)
