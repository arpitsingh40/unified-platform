"""Revenue Router — stub. Registers at /api/revenue."""
from fastapi import APIRouter
router = APIRouter(prefix="/api/revenue", tags=["revenue"])

@router.get("/status")
def revenue_status():
    return {"status": "stub", "message": "Wire revenue_engine + Zoho to enable revenue pipelines (invoicing/retention). Factory and growth loops run independently."}
