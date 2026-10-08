"""Business Builder Router — stub. Registers at /api/builder."""
from fastapi import APIRouter
router = APIRouter(prefix="/api/builder", tags=["builder"])

@router.get("/status")
def builder_status():
    return {"status": "stub", "message": "Builder is served via /api/factory/build (factory_bridge + factory_router). This is the legacy route."}
