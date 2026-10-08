"""Business Builder — minimal stubs so factory_bridge and server boot without the full Smartdecision-main business_builder.py.

When the full module is ported, replace this with the real one. API is intentionally compatible:
  run_audit(idea, twin) -> dict
  build_blueprint(idea, twin, audit) -> dict
  create_build_record(...) -> dict
  ensure_builder_startup() -> None
"""
from __future__ import annotations
import logging
from typing import Optional

log = logging.getLogger("builder_stub")

def run_audit(idea: str, twin: Optional[dict] = None) -> dict:
    return {"decision": "GO", "score": 7.2, "gates": [], "note": "audit stub — wire business_builder + Tavily for 8-gate scored audit"}

def build_blueprint(idea: str, twin: Optional[dict] = None, audit: Optional[dict] = None) -> dict:
    return {
        "idea": idea[:400] if idea else "",
        "pricing": {"range": "₹599–₹1,999", "avg": 1399, "margin": "65%", "valuationMultiple": 2.5},
        "icp": {"who": "Gen Z women, 18–26, Tier 1 India", "pain": "trend access + sizing", "channel": "Instagram + WhatsApp"},
        "revenue_path": "weekly drops → UGC flywheel → COD→repeat",
        "note": "blueprint stub — wire full business_builder for pricing/ICP/revenue_path generation",
    }

def create_build_record(user_id: str, org_id: str, vision: str, category_id: str = "", twin: Optional[dict] = None, audit: Optional[dict] = None, blueprint: Optional[dict] = None) -> dict:
    try:
        from db import db as _db
        if _db is not None:
            col = _db.business_builds
            import uuid
            from datetime import datetime, timezone
            doc = {"id": f"build_{uuid.uuid4().hex[:8]}", "user_id": user_id, "org_id": org_id, "vision": vision, "category_id": category_id, "twin": twin or {}, "audit": audit or {}, "blueprint": blueprint or {}, "status": "built", "created_at": datetime.now(timezone.utc).isoformat()}
            col.insert_one(doc)
            return doc
    except Exception as e:
        log.warning(f"create_build_record stub failed: {e}")
    return {"ok": True, "stub": True}

def ensure_builder_startup():
    return
