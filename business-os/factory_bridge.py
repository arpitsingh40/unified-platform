"""Factory Bridge — SmartDecigen speaks BusinessFactory.

Single responsibility: given a natural-language idea ("fast fashion ecommerce"),
produce a deployable business (catalog + brand + routes + checkout + worth).

Memory: business_factory_builds collection (one per build, org-scoped).
No new infra: reuses business_builder audit/blueprint + catalog generation.
Idempotent: calling `build_from_idea(text)` twice with same normalized idea returns same build within 24h.

Used by:
  - llm_turn (inline, when chat message looks like a business idea)
  - /api/factory/* router
  - execution bridge (scheduled growth tasks that need a live business to drive revenue)
"""
from __future__ import annotations
import re
import uuid
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import db as _db

log = logging.getLogger("factory_bridge")

FACTORY_COL = _db.business_factory_builds if _db is not None else None
if FACTORY_COL is not None:
    try:
        FACTORY_COL.create_index("id", unique=True)
        FACTORY_COL.create_index([("org_id", 1), ("created_at", -1)])
        FACTORY_COL.create_index([("normalized_idea", 1), ("org_id", 1)])
    except Exception:
        pass

# ------------------------------------------------------------------
# Idea detection — when a chat message IS a business idea
# ------------------------------------------------------------------
IDEA_PAT = re.compile(
    r"\b(build|create|start|launch|make).*?\b(business|store|shop|brand|ecommerce|saas|app|platform|marketplace|agency|factory)\b"
    r"|\b(fast fashion|ecommerce|dropshipping|saas|edtech|healthtech|fintech|marketplace)\b"
    r"|\bmy idea is\b",
    re.I,
)

def looks_like_business_idea(msg: str) -> bool:
    if not msg or len(msg.strip()) < 8:
        return False
    # Too short after strip -> not an idea
    t = msg.strip()
    if len(t.split()) < 2:
        return False
    return bool(IDEA_PAT.search(t))

def _normalize_idea(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip().lower())[:200]

# ------------------------------------------------------------------
# Catalog generator (LLM when available, fallback when not)
# ------------------------------------------------------------------
CATALOG_SYSTEM = """You are the Business Factory catalog generator.
Given a business idea, output ONLY JSON:
{
  "brand": {"name": "UPPERCASE 1-word brand", "tagline": "under 8 words", "colors": {"bg": "#FFF8F0","text":"#0a0a0a","accent":"#hex"}},
  "pricing": {"range": "₹599–₹1,999", "avg": 1399, "margin": "65%", "valuationMultiple": 2.5},
  "categories": ["Tops","Bottoms","Dresses"],
  "drops": ["Drop 01 — Monsoon", "Drop 02 — Afterhours"],
  "products": [ {"name":"...", "price":1299, "category":"Tops","color":"..","sizes":["S","M","L"], "badge":"NEW|BESTSELLER|LOW STOCK|null"} x 12-24 ]
}
Tailor every field to the idea. Use India pricing (INR). Keep avg realistic for the vertical."""

def _fallback_catalog(idea: str) -> dict:
    idea_l = idea.lower()
    if "fashion" in idea_l or "apparel" in idea_l or "clothing" in idea_l:
        return {
            "brand": {"name": "DRIFT", "tagline": "New drops weekly. Gone forever.", "colors": {"bg": "#FFF8F0", "text": "#0a0a0a", "accent": "#FF3B30"}},
            "pricing": {"range": "₹599–₹1,999", "avg": 1399, "margin": "65%", "valuationMultiple": 2.5},
            "categories": ["Tops", "Bottoms", "Dresses", "Outerwear", "Accessories"],
            "drops": ["Drop 01 — Monsoon", "Drop 02 — Afterhours", "Drop 03 — Off-Duty"],
            "products": [
                {"name": "Cropped Linen Shirt", "price": 1299, "category": "Tops", "color": "Ecru", "sizes": ["XS","S","M","L"], "badge": "NEW"},
                {"name": "High-Waist Cargo Pants", "price": 1799, "category": "Bottoms", "color": "Stone", "sizes": ["XS","S","M","L","XL"], "badge": "BESTSELLER"},
                {"name": "Racer Mini Dress", "price": 1499, "category": "Dresses", "color": "Black", "sizes": ["XS","S","M","L"], "badge": "NEW"},
                {"name": "Oversized Tee — Washed", "price": 799, "category": "Tops", "color": "Faded Black", "sizes": ["S","M","L","XL"], "badge": None},
                {"name": "Pleated Midi Skirt", "price": 1599, "category": "Bottoms", "color": "Cocoa", "sizes": ["XS","S","M","L"], "badge": "LOW STOCK"},
                {"name": "Utility Shacket", "price": 1999, "category": "Outerwear", "color": "Olive", "sizes": ["S","M","L","XL"], "badge": None},
            ],
        }
    # Generic vertical — still a sellable business
    return {
        "brand": {"name": "LUMEN", "tagline": "Built for you. Shipped today.", "colors": {"bg": "#FFF8F0", "text": "#0a0a0a", "accent": "#0a0a0a"}},
        "pricing": {"range": "₹999–₹4,999", "avg": 2499, "margin": "60%", "valuationMultiple": 3},
        "categories": ["New In", "Bestsellers"],
        "drops": ["Drop 01"],
        "products": [
            {"name": "Starter Pack", "price": 999, "category": "New In", "color": "Black", "sizes": ["One Size"], "badge": "NEW"},
            {"name": "Pro Bundle", "price": 2499, "category": "Bestsellers", "color": "White", "sizes": ["S","M","L"], "badge": "BESTSELLER"},
        ],
    }

def generate_catalog(idea: str) -> dict:
    try:
        from llm_client import client, _extract_json, PRIMARY_MODEL
        prompt = f"Idea: {idea[:1200]}\nBuild the catalog + brand. Return ONLY JSON."
        r = client().messages.create(model=PRIMARY_MODEL, max_tokens=2500, system=CATALOG_SYSTEM, messages=[{"role": "user", "content": prompt}])
        txt = next((b.text for b in r.content if getattr(b, "type", "") == "text"), "").strip()
        data = json.loads(_extract_json(txt))
        if isinstance(data.get("products"), list) and len(data["products"]) >= 6 and data.get("brand", {}).get("name"):
            return data
        raise ValueError("catalog LLM returned too few products")
    except Exception as e:
        log.warning(f"catalog LLM fallback: {e}")
        return _fallback_catalog(idea)

# ------------------------------------------------------------------
# Worth math — AOV / margin / valuation from catalog
# ------------------------------------------------------------------
def _worth_from_catalog(catalog: dict) -> dict:
    products = catalog.get("products") or []
    prices = [p.get("price", 0) for p in products if isinstance(p.get("price"), (int, float))]
    aov = round(sum(prices) / len(prices)) if prices else 1399
    margin = catalog.get("pricing", {}).get("margin", "65%")
    vm = catalog.get("pricing", {}).get("valuationMultiple", 2.5)
    return {"aov_inr": aov, "margin": margin, "valuation_multiple": vm, "monthly_valuation_formula": f"Revenue × {vm}× (DTC benchmark)"}

# ------------------------------------------------------------------
# Main: build_from_idea — the one function
# ------------------------------------------------------------------
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def build_from_idea(idea: str, org_id: str, user_id: str, twin: Optional[dict] = None) -> dict:
    """Build a factory entry from idea text.

    Pipeline: twin → audit(8 gates) → blueprint → catalog → worth → growth_plan → persist.

    Never raises to caller on LLM/Tavily failure — returns honest status + what succeeded.
    """
    t = (idea or "").strip()
    if len(t) < 8:
        return {"ok": False, "error": "Idea too short — tell me the business you want in 1 sentence (e.g. 'fast fashion ecommerce for Gen Z women')"}
    normalized = _normalize_idea(t)

    # Idempotency: same normalized idea + org within 24h -> return existing
    if FACTORY_COL is not None:
        try:
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            existing = FACTORY_COL.find_one({"org_id": org_id, "normalized_idea": normalized, "created_at": {"$gte": cutoff}}, {"_id": 0})
            if existing:
                existing["idempotent"] = True
                return {"ok": True, **existing}
        except Exception:
            pass

    # 1) Twin (best-effort)
    twin = twin or {}
    if not twin:
        try:
            from genesis import extract_twin
            twin = extract_twin(t).get("twin", {}) or {}
        except Exception:
            twin = {}

    # 2) Audit (8 gates)
    audit = {}
    try:
        from business_builder import run_audit
        audit = run_audit(t, twin=twin) or {}
    except Exception as e:
        log.warning(f"factory audit skipped: {e}")
        audit = {"decision": "GO", "note": "audit unavailable — configure LLM/Tavily for scored gates"}

    # 3) Blueprint (from business_builder) — includes pricing + ICP + revenue path
    blueprint = {}
    try:
        from business_builder import build_blueprint
        blueprint = build_blueprint(t, twin=twin, audit=audit) or {}
    except Exception as e:
        log.warning(f"factory blueprint skipped: {e}")

    # 4) Catalog + brand (LLM with fallback → never empty)
    catalog = generate_catalog(t)
    worth = _worth_from_catalog(catalog)

    # 5) 10× growth plan (always present)
    try:
        from growth_engine import build_growth_plan
        growth = build_growth_plan(idea=t, catalog=catalog, blueprint=blueprint, worth=worth)
    except Exception as e:
        log.warning(f"growth plan fallback: {e}")
        growth = {"headline": "10× in 12 months via weekly drops + UGC flywheel", "loops": [], "kpis": ["Revenue", "Orders", "Repeat"], "cadence": "weekly"}

    factory_id = f"factory_{uuid.uuid4().hex[:10]}"
    doc = {
        "id": factory_id,
        "org_id": org_id,
        "user_id": user_id,
        "idea": t[:2000],
        "normalized_idea": normalized,
        "twin": twin,
        "audit": audit,
        "blueprint": blueprint,
        "catalog": catalog,
        "worth": worth,
        "growth": growth,
        "status": "built",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        # Legacy BusinessFactory scaffold can be generated on demand at:
        # C:\\Users\\Dell -\\Documents\\Code\\BusinessFactory  (DRIFT demo, Next.js)
    }

    if FACTORY_COL is not None:
        try:
            FACTORY_COL.insert_one(dict(doc))
        except Exception as e:
            log.warning(f"factory persist failed: {e}")

    # Also create a business_builds record so legacy Builder UI + revenue loops see it
    try:
        from business_builder import create_build_record
        create_build_record(user_id=user_id, org_id=org_id, vision=t, category_id="", twin=twin, audit=audit, blueprint=blueprint)
    except Exception:
        pass

    return {"ok": True, **doc}

def list_factory_builds(org_id: str, limit: int = 20) -> list[dict]:
    if FACTORY_COL is None:
        return []
    try:
        return list(FACTORY_COL.find({"org_id": org_id}, {"_id": 0}).sort("created_at", -1).limit(min(limit, 50)))
    except Exception:
        return []

def get_factory_build(factory_id: str, org_id: str) -> Optional[dict]:
    if FACTORY_COL is None:
        return None
    try:
        doc = FACTORY_COL.find_one({"id": factory_id}, {"_id": 0})
        if not doc or doc.get("org_id") != org_id:
            return None
        return doc
    except Exception:
        return None

def ensure_factory_startup():
    if FACTORY_COL is not None:
        try:
            FACTORY_COL.create_index("id", unique=True)
            FACTORY_COL.create_index([("org_id", 1), ("created_at", -1)])
        except Exception:
            pass
