"""Capability API — build anything from websites to reports to campaigns."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from security import current_user
from capabilities import (CAPABILITIES, route_capability, execute_capability,
                          iterate_capability, BUILDS)

# Capability platform API routes
router = APIRouter(prefix="/api/capabilities", tags=["capabilities"])


# Request body for building a capability
class BuildIn(BaseModel):
    description: str = Field(min_length=10, max_length=2000)
    type: Optional[str] = Field(default=None, max_length=50)
    deploy: bool = Field(default=True)


# Request body for iterating a build
class IterateIn(BaseModel):
    build_id: str = Field(min_length=5)
    feedback: str = Field(min_length=5, max_length=1000)


# List all capability types
@router.get("")
def list_capabilities(user: dict = Depends(current_user)):
    """List all 15 capability types with trigger keywords."""
    result = {}
    for ctype, cap in CAPABILITIES.items():
        result[ctype] = {
            "label": cap["label"],
            "description": cap["description"],
            "trigger_keywords": cap["trigger_kw"][:5],
            "deploy_platform": cap["deploy_platform"],
            "output_format": cap["output_format"],
            "metrics": cap["metrics"],
        }
    return {"types": len(result), "capabilities": result}


# Generate and deploy a capability
@router.post("/build")
def create_capability(body: BuildIn, user: dict = Depends(current_user)):
    """Generate and deploy a capability from description.
    Auto-routes to the right type if not specified."""
    result = execute_capability(body.description, body.type, body.deploy)
    if result.get("status") == "failed":
        raise HTTPException(502, f"Failed at {result.get('step')}: {result.get('error', 'unknown error')}")
    return result


# Iterate on an existing build
@router.post("/iterate")
def iterate_capability_endpoint(body: IterateIn, user: dict = Depends(current_user)):
    """Iterate on an existing build with feedback."""
    result = iterate_capability(body.build_id, body.feedback)
    if result.get("error"):
        raise HTTPException(404, result["error"])
    return result


# List recent builds
@router.get("/builds")
def list_builds(user: dict = Depends(current_user)):
    """List recent capability builds."""
    builds = list(BUILDS.values())[-20:]
    return {"builds": builds, "count": len(builds)}


# Test capability routing for a message
@router.post("/route")
def route_message(body: dict, user: dict = Depends(current_user)):
    """Test: what capability type would this message route to?"""
    message = body.get("message", "")
    route = route_capability(message)
    return {"message": message[:200], "routed_to": route["type"] if route else None,
            "label": route["label"] if route else "No match"}
