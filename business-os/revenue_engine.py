"""Revenue Engine — stub for unified-platform monorepo.
Real engine lives in Smartdecision-main/revenue_engine.py (not yet ported).
This stub keeps the Business OS bootable: startup no-op, cron no-op, Zoho honesty.
"""
def ensure_revenue_startup():
    return

def run_revenue_cycle(org_id: str, pipelines=None):
    # No-op stub — returns honest status until full engine is ported
    return {"org_id": org_id, "pipelines": pipelines or [], "status": "stub — wire Zoho/revenue_engine to enable", "ran": 0}
