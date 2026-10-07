"""
Business Genesis Engine — deploy an entire company in 15 minutes.

Pipeline:
  1. extract_twin(founder_input) → FounderDigitalTwin + challenge questions
  2. generate_mission(twin, answers) → Mission + North Star + Strategy
  3. generate_organization(twin, mission) → Divisions + Executives + Culture
  4. map_capabilities(twin, org) → Required tools + connection checklist
  5. launch_execution(org) → Per-executive first-week tasks at L3
"""

import json
import logging
from typing import Optional

from ontology import (
    Mission, Strategy, Goal, Division, ExecutiveState, KPI,
    AuthorityLevel, ExecutiveStatus, new_id, utcnow,
)
from llm_client import client, _extract_json, ULTRA_MODEL, PRIMARY_MODEL

log = logging.getLogger("genesis")

# Master prompt for all genesis generation calls
GENESIS_SYSTEM = """You are the Genesis Engine of SmartDecigen. Your job is to take a founder's raw business description and transform it into the structural blueprint for a company.

You think like a world-class startup advisor who has seen thousands of companies succeed and fail. Your output must be specific, grounded in the founder's actual situation, and immediately actionable — not generic, not aspirational.

RULES:
1. Every output field must reference specific details from the founder's input — never fill with placeholders
2. Numbers must be concrete estimates based on what the founder shared (ARR, team size, runway, industry)
3. If the founder didn't share a detail, say "unknown" — never invent
4. Executive roles must match the industry (a solar company needs different roles than a SaaS company)
5. KPIs must be measurable and time-bound
6. Decision rules must be brutally practical — things a real founder would actually follow

Return ONLY valid JSON. No markdown fences."""


def extract_twin(founder_input: str) -> dict:
    """Extract a Founder Digital Twin and challenge questions from raw input.
    1 LLM call — ~3-5 seconds."""
    prompt = f"""FOUNDER INPUT: {founder_input}

EXTRACT:
1. A DIGITAL TWIN of this founder with these fields:
   - industry, stage (idea/pre-revenue/growth/scale)
   - current_arr, current_arr_currency (₹ or $), team_size, runway_months
   - constraints (money, talent, time, regulation, technology)
   - fears (what keeps them awake at night)
   - strategic_forks (the 2-4 big decisions they are wrestling with)
   - founder_bottleneck (the thing they personally are the blocker on)
   - what_they_have (assets: revenue? customers? IP? team? distribution?)

2. 3-5 SHARP CHALLENGE QUESTIONS that SALAAR would ask — the kind that make the founder stop and think. Each question should target a gap or assumption in their thinking. Examples: "Which of your three forks dies first if you had to choose today?", "You said 13 months runway but didn't mention burn rate — what is your actual monthly burn?", "If you could fire yourself from one decision you make daily, which one?"

Return JSON:
{{"twin": {{"industry": "...", "stage": "...", "current_arr": 0, "currency": "₹", "team_size": 0, "runway_months": 0, "constraints": ["..."], "fears": ["..."], "strategic_forks": ["..."], "founder_bottleneck": "...", "what_they_have": ["..."]}}, "questions": ["question 1", "question 2", "question 3"]}}"""

    try:
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=1500, system=GENESIS_SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"extract_twin failed: {e}")
        return {
            "twin": {
                "industry": "unknown", "stage": "growth", "current_arr": 0, "currency": "₹",
                "team_size": 0, "runway_months": 12, "constraints": [], "fears": [],
                "strategic_forks": [], "founder_bottleneck": "unknown", "what_they_have": []
            },
            "questions": []
        }


def generate_mission(twin: dict, answers: dict = None) -> dict:
    """Generate Mission, North Star, Strategy, and Decision Rules from the Digital Twin.
    1 LLM call."""
    twin_str = json.dumps(twin, indent=2)
    answers_str = json.dumps(answers, indent=2) if answers else "(no answers yet)"

    prompt = f"""DIGITAL TWIN:
{twin_str}

FOUNDER'S ANSWERS TO CHALLENGE QUESTIONS:
{answers_str}

Generate the COMPANY MISSION AND STRATEGY:

1. MISSION STATEMENT — 1 powerful sentence that defines what this company exists to do and for whom. Make it specific to their industry and stage.

2. NORTH STAR — 1 sentence. The 10-year outcome. Ambitious but grounded in their actual trajectory.

3. TARGET — Numerical target with timeframe (example: "₹50 crore ARR by 2028, ₹1000 crore by 2036")

4. DEADLINE — Year for the ultimate target.

5. PRIORITIES — 4-6 ranked priorities for the next 12-18 months. Each must be concrete and reference their actual constraints (team size, runway, market). Example: "1. Fix engineering velocity — 3x shipping speed with current 2 engineers before hiring more"

6. DECISION RULES — 3-4 brutally practical rules the founder can use to make decisions without you. Example: "Ship features only after 3 customer conversations validate need. Kill any channel with <3% conversion within 60 days. Raise funding only when execution is consistent for 3 consecutive months."

7. OBJECTIVE — 1 sentence: "What should the next 90 days prove?"

Return JSON:
{{"mission": "...", "north_star": "...", "target": "...", "deadline": "...", "priorities": ["..."], "decision_rules": "...", "next_90_days_objective": "..."}}"""

    try:
        r = client().messages.create(model=ULTRA_MODEL, max_tokens=1200, system=GENESIS_SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"generate_mission failed: {e}")
        return {
            "mission": f"Build a successful {twin.get('industry', 'business')}",
            "north_star": f"Become the leader in {twin.get('industry', 'the market')}",
            "target": "Grow revenue", "deadline": "2028",
            "priorities": ["Ship product", "Get customers", "Build team"],
            "decision_rules": "Ship fast. Talk to customers every week.",
            "next_90_days_objective": "Prove product-market fit"
        }


def generate_organization(twin: dict, mission: dict) -> dict:
    """Generate the organization structure — divisions, executives with roles/missions/KPIs/budgets.
    1 LLM call with Ultra model for quality."""

    twin_str = json.dumps(twin, indent=2)
    mission_str = json.dumps(mission, indent=2)

    prompt = f"""FOUNDER PROFILE:
{twin_str}

MISSION & STRATEGY:
{mission_str}

DESIGN THE ORGANIZATION. This must feel like a REAL company structure, not a template.

Generate 4-7 DIVISIONS. Each division has 1-3 EXECUTIVES. Every executive must have:

- role: Title that matches the industry (not generic "VP Sales" — make it specific: "VP Institutional Solar Sales")
- department_function: One of sales, marketing, product, engineering, operations, finance, leadership, general
- mission: 1-2 sentences. What THIS executive is accountable for. Specific to their role and the company's stage.
- spending_limit_inr: Budget in ₹ (proportional to the company's ARR — a ₹5.8cr company should NOT have ₹5cr budgets per exec)
- authority_level: "L3" (recommend-only at birth — this is non-negotiable per the Constitution)
- kpis: 2-3 KPIs with name, target (specific number), weight (1-10)
- knowledge_domains: 3-5 relevant domains this executive needs expertise in

Additionally, 4-5 CULTURE PRINCIPLES for this company:
- statement: 1 sentence principle
- heuristic: 1 practical rule
- anti_pattern: 1 behavior to avoid
- weight: 1-10

Return JSON:
{{"divisions": [{{"name": "...", "function": "...", "executives": [{{"role": "...", "department_function": "...", "mission": "...", "spending_limit_inr": 0, "authority_level": "L3", "kpis": [{{"name": "...", "target": "...", "weight": 10}}], "knowledge_domains": ["..."]}}]}}], "culture": [{{"statement": "...", "heuristic": "...", "anti_pattern": "...", "weight": 10}}]}}"""

    try:
        r = client().messages.create(model=ULTRA_MODEL, max_tokens=3000, system=GENESIS_SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        return json.loads(_extract_json(txt))
    except Exception as e:
        log.error(f"generate_organization failed: {e}")
        return {"divisions": [], "culture": []}


def map_capabilities(twin: dict) -> list[dict]:
    """Deterministic mapping: business model → required capabilities → tools to connect."""
    industry = (twin.get("industry") or "").lower()
    caps = []

    # Every business
    caps.extend([
        {"capability": "email", "why": "Customer + internal communication", "toolkits": ["gmail", "outlook"]},
        {"capability": "customer_relationship", "why": "Track customers and deals", "toolkits": ["zoho"]},
        {"capability": "invoicing", "why": "Bill customers and get paid", "toolkits": ["zoho_invoice", "zoho_books"]},
        {"capability": "calendar", "why": "Schedule meetings and deadlines", "toolkits": ["googlecalendar"]},
    ])

    # Industry-specific
    if any(kw in industry for kw in ["solar", "energy", "construction", "manufacturing", "real estate", "logistics"]):
        caps.append({"capability": "geolocation", "why": "Site surveys and location planning", "toolkits": ["google_maps", "mapbox"]})
        caps.append({"capability": "project_management", "why": "Track installations and site work", "toolkits": ["jira", "asana", "linear"]})

    if any(kw in industry for kw in ["saas", "software", "ai", "tech", "app"]):
        caps.append({"capability": "code_review", "why": "Build and ship the product", "toolkits": ["github", "gitlab"]})
        caps.append({"capability": "ci_cd", "why": "Automate deployments", "toolkits": ["github", "vercel"]})
        caps.append({"capability": "monitoring", "why": "Know when production breaks", "toolkits": ["datadog", "sentry"]})

    if any(kw in industry for kw in ["retail", "ecommerce", "shop", "store"]):
        caps.append({"capability": "ecommerce", "why": "Run online store", "toolkits": ["shopify", "woocommerce"]})

    caps.append({"capability": "payment_processing", "why": "Accept payments", "toolkits": ["stripe", "razorpay"]})

    return caps


# ── Demo ──
if __name__ == "__main__":
    test_input = "I want to build India's largest AI-powered solar company. ₹5.8 crore ARR, 27 employees, 13 months runway. Engineering is slow, sales lumpy, I'm the bottleneck."
    print("Extracting Digital Twin...")
    twin_data = extract_twin(test_input)
    print(json.dumps(twin_data, indent=2)[:500])
    print(f"\nQuestions: {len(twin_data.get('questions', []))}")
    print(f"Capabilities needed: {len(map_capabilities(twin_data.get('twin', {})))}")
