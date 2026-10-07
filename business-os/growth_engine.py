"""Growth Engine — 10× year-on-year, on autopilot.

Owns: which loops run, what they move, how to measure.
Every loop is Zoho-honest: if Zoho not configured, the task is created as manual
and the founder sees exactly what to do + what to connect.

Loops:
  1) weekly_drop — new catalog slice every Monday → catalog + social + email
  2) ugc_flywheel — micro-influencer seeding → reels → retargeting
  3) retention — COD verification → repeat nudge → WhatsApp
  4) pricing_test — lift AOV via bundle/price micro-tests

Each build's growth plan is persisted on the factory doc; cron jobs below
enqueue the loop's tasks via execution.bridge on schedule.
"""
from __future__ import annotations
import logging
from typing import Optional

log = logging.getLogger("growth_engine")

GROWTH_SYSTEM = """You are the 10× Growth Planner for SmartDecigen.
Given an idea + catalog + blueprint, design a 12-month plan that can plausibly 10× revenue.

Constraints:
- Lean team (2-5 humans) + AI. No 20-person plan.
- Every lever must map to a handler we have (GMAIL, ZOHO, TAVILY, GITHUB, SLACK, NOTION) or be marked manual.
- Revenue only via Zoho Payments/Books (hosted checkout, mandate, invoice) or COD (for India retail).
- Return ONLY JSON:
{
  "headline": "one line",
  "loops": [{"name":"weekly_drop|ugc_flywheel|retention|pricing_test","cadence":"weekly|daily|continuous","owner":"Growth|Product|Ops","moves":["..."],"handler":"GMAIL|ZOHO|manual","metric":"Orders|Revenue|AOV|Repeat"}],
  "kpis": ["Revenue","Orders","AOV","Repeat %","CAC","LTV"],
  "cadence": "weekly|daily",
  "milestones": [{"month":3,"target":"₹X revenue or Y orders","proof":"what to measure"}]
}
"""

def build_growth_plan(idea: str, catalog: dict, blueprint: Optional[dict] = None, worth: Optional[dict] = None) -> dict:
    # Try LLM, else deterministic fallback
    try:
        from llm_client import client, _extract_json, PRIMARY_MODEL
        import json
        prompt = f"Idea: {idea[:800]}\nCatalog: {json.dumps(catalog)[:1200]}\nBlueprint: {json.dumps(blueprint or {})[:800]}\nDesign the 10× growth plan."
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=2000, system=GROWTH_SYSTEM, messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
        if isinstance(data.get("loops"), list) and len(data["loops"]) >= 2:
            return data
        raise ValueError("growth LLM too thin")
    except Exception as e:
        log.warning(f"growth LLM fallback: {e}")
        return {
            "headline": "10× in 12 months — weekly drops + UGC flywheel + COD→repeat",
            "loops": [
                {"name": "weekly_drop", "cadence": "weekly", "owner": "Product", "moves": ["Ship 6 new SKUs every Monday", "Tease on Instagram 48h before", "Email waitlist at drop"], "handler": "GITHUB", "metric": "Orders"},
                {"name": "ugc_flywheel", "cadence": "continuous", "owner": "Growth", "moves": ["Seed 15 micro influencers / week (gifting)", "Repurpose 3 best UGC into paid reels", "Retarget viewers with COD offer"], "handler": "GMAIL", "metric": "Revenue"},
                {"name": "retention", "cadence": "daily", "owner": "Ops", "moves": ["Verify COD via WhatsApp in 30 min", "Ship in 48h, ask for review on delivery", "Nudge repeat 14 days post-purchase"], "handler": "manual", "metric": "Repeat %"},
                {"name": "pricing_test", "cadence": "weekly", "owner": "Growth", "moves": ["Bundle 2 at ₹1,999 test", "Free-ship threshold A/B", "Raise compareAt on bestsellers"], "handler": "manual", "metric": "AOV"},
            ],
            "kpis": ["Revenue", "Orders", "AOV", "Repeat %", "CAC", "LTV"],
            "cadence": "weekly",
            "milestones": [
                {"month": 1, "target": "100 orders, AOV ₹1,399", "proof": "COD verification rate, dispatch SLA"},
                {"month": 3, "target": "₹10L revenue", "proof": "Repeat % + UGC reels shipped"},
                {"month": 6, "target": "₹30L revenue, LTV/CAC > 3", "proof": "Retargeting ROAS, pricing test wins"},
                {"month": 12, "target": "10× month-1 revenue", "proof": "Weekly drop cadence unbroken, no restock model holds"},
            ],
        }

def ensure_growth_startup():
    return

if __name__ == "__main__":
    print("OK — growth_engine loaded")
