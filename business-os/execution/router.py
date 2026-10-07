"""Execution API — public surface for the Execution Runtime.
Endpoints: connection status, tool listing, plan execution, tool connections.
Self-hosted MCP gateway — Python handlers for each service, 1403 toolkits in catalog.
"""
import uuid
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional

from security import current_user
from db import members_col

from .mcp_client import (
    list_tools, search_tools, call_tool, mcp_enabled,
    tools_for_department, tools_for_founder,
    is_connected, linked_toolkits,
)
from .dispatcher import execute_plan, validate_plan
from .collector import collect_execution_result
from .connections import (
    get_available_integrations, get_org_connections,
    init_connection, complete_connection, disconnect_toolkit,
    suggest_tools_for_function, suggest_tools_for_at_risk,
    refresh_connections_from_composio,
)
from .workflows import match_workflows, workflow_to_execution_plan, WORKFLOWS

log = logging.getLogger("execution.router")
router = APIRouter(prefix="/api/execution")


# Request body for connection initiation
class ConnectIn(BaseModel):
    toolkit: str = Field(min_length=2, max_length=100)
    redirect_uri: Optional[str] = Field(default=None, max_length=500)


# Request body for completing a connection
class CompleteIn(BaseModel):
    toolkit: str = Field(min_length=2, max_length=100)


# Request body for disconnecting a toolkit
class DisconnectIn(BaseModel):
    toolkit: str = Field(min_length=2, max_length=100)


# Fetch active membership record for user
def _active_membership(user: dict) -> Optional[dict]:
    return members_col.find_one({"user_id": user["id"], "status": "active"})


# Resolve user's org id from membership
def _org_for_user(user: dict) -> Optional[str]:
    m = _active_membership(user)
    return m["org_id"] if m else None


# Resolve user's department function
def _department_for_user(user: dict) -> str:
    return (user.get("function") or "general")


# MCP health and connection status
@router.get("/status")
def execution_status(user: dict = Depends(current_user)):
    """MCP health: CLI installed? logged in? toolkits connected?"""
    if not mcp_enabled():
        return {"mcp_enabled": False, "message": "Set a service token (e.g. GMAIL_ACCESS_TOKEN) in .env"}

    connected = is_connected()
    toolkits = linked_toolkits() if connected else []
    tools = list_tools() if connected else []

    return {
        "mcp_enabled": True,
        "cli_installed": True,
        "authenticated": connected,
        "connected_toolkits": toolkits,
        "tools_available": len(tools),
    }


# List tools available to user's department
@router.get("/tools")
def get_tools(query: Optional[str] = None, user: dict = Depends(current_user)):
    """List tools available to this user's department."""
    if not mcp_enabled():
        return {"tools": [], "mcp_enabled": False}

    if not is_connected():
        return {"tools": [], "mcp_enabled": True, "authenticated": False}

    m = _active_membership(user)
    if m and m.get("role") == "owner":
        tools = tools_for_founder()
    else:
        tools = tools_for_department(_department_for_user(user))

    if query:
        tools = search_tools(query)

    return {"tools": tools, "count": len(tools), "mcp_enabled": True, "authenticated": True}


# Execute a full tool plan (owner-only)
@router.post("/execute")
def execute(body: dict, user: dict = Depends(current_user)):
    """Execute a plan of tool calls. Owner-only."""
    if not mcp_enabled():
        raise HTTPException(503, "MCP disabled")
    if not is_connected():
        raise HTTPException(412, "No connected services — set service tokens in .env")

    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    if m["role"] != "owner":
        raise HTTPException(403, "Only workspace owner")

    plan = body.get("plan", body)
    if not plan.get("actions"):
        raise HTTPException(422, "Plan must contain 'actions' array")

    issues = validate_plan(plan)
    if issues:
        return {"status": "rejected", "issues": issues}

    dept = "leadership" if m["role"] == "owner" else _department_for_user(user)
    result = execute_plan(plan, dept)
    return {
        "execution_id": "exec_" + uuid.uuid4().hex[:16],
        "status": "completed",
        "actions": result["actions"],
        "summary": result["summary"],
    }


# Execute a single named tool
@router.post("/tools/{tool_name}")
def execute_single_tool(tool_name: str, body: dict, user: dict = Depends(current_user)):
    """Execute a single tool."""
    if not mcp_enabled():
        raise HTTPException(503, "MCP disabled")
    if not is_connected():
        raise HTTPException(412, "Not authenticated")

    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    if m["role"] != "owner":
        raise HTTPException(403, "Only workspace owner")

    result = call_tool(tool_name, body.get("args", {}))

    return {
        "tool": tool_name,
        "result": result.get("result", "")[:2000],
        "error": result.get("error", ""),
        "successful": result.get("successful", False),
        "elapsed_ms": result.get("execution_time_ms", 0),
    }


# List connected toolkits
@router.get("/toolkits")
def get_linked_toolkits(user: dict = Depends(current_user)):
    """List connected toolkits (Gmail, GitHub, etc)."""
    if not mcp_enabled() or not is_connected():
        return {"toolkits": [], "authenticated": False}
    return {"toolkits": linked_toolkits(), "authenticated": True}


# ======================================================================
# Connection management endpoints
# ======================================================================

# List available integrations with status
@router.get("/connections")
def list_connections(user: dict = Depends(current_user)):
    """List all available integrations (1,403 toolkits) with connection status."""
    m = _active_membership(user)
    org_id = m["org_id"] if m else None
    category = None  # ponytail: add query param later when UI supports filters

    integrations = get_available_integrations(org_id, category)
    connected = [i for i in integrations if i["connected"]]
    available = [i for i in integrations if not i["connected"]]

    return {
        "total": len(integrations),
        "connected": len(connected),
        "available": len(available),
        "connected_list": connected,
        "top_available": available[:20],
    }


# Quick connection status and suggestions
@router.get("/connections/status")
def connection_status(user: dict = Depends(current_user)):
    """Quick status: what's connected, what's suggested."""
    m = _active_membership(user)
    org_id = m["org_id"] if m else None

    active = get_org_connections(org_id) if org_id else []
    at_risk_suggestions = suggest_tools_for_at_risk(org_id) if org_id else {}

    return {
        "active_connections": len(active),
        "connected_tools": [c["toolkit"] for c in active],
        "at_risk_suggestions": at_risk_suggestions,
    }


# Recommend tools for a business function
@router.get("/connections/suggest/{function}")
def suggest_for_function(function: str, user: dict = Depends(current_user)):
    """Recommend tools for a specific business function."""
    m = _active_membership(user)
    org_id = m["org_id"] if m else None
    return {"function": function, "tools": suggest_tools_for_function(function, org_id)}


# Initiate OAuth connection for a toolkit
@router.post("/connections/connect")
def connect_toolkit(body: ConnectIn, user: dict = Depends(current_user)):
    """Initiate OAuth connection for a toolkit. Returns auth URL."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    if m["role"] != "owner":
        raise HTTPException(403, "Only workspace owner can connect tools")

    result = init_connection(m["org_id"], body.toolkit, body.redirect_uri)

    if "error" in result:
        raise HTTPException(502, result["error"])
    if result.get("already_connected"):
        return {"status": "already_connected", "connection_id": result["connection_id"]}

    return {
        "status": "pending",
        "connection_id": result["connection_id"],
        "toolkit": body.toolkit,
        "auth_url": result["auth_url"],
        "instructions": result.get("instructions", "Complete OAuth to connect."),
    }


# Complete OAuth connection callback
@router.post("/connections/complete")
def complete_toolkit_connection(body: CompleteIn, user: dict = Depends(current_user)):
    """Mark a toolkit connection as complete after OAuth. Called by frontend/callback."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")

    result = complete_connection(m["org_id"], body.toolkit)
    # Sync with Composio to refresh tool availability
    try:
        refresh_connections_from_composio(m["org_id"])
    except Exception:
        pass
    return result


# Disconnect a toolkit for the org
@router.post("/connections/disconnect")
def disconnect_toolkit_endpoint(body: DisconnectIn, user: dict = Depends(current_user)):
    """Disconnect a toolkit for this org."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    if m["role"] != "owner":
        raise HTTPException(403, "Only workspace owner can disconnect tools")

    return disconnect_toolkit(m["org_id"], body.toolkit) if m else {"error": "No org"}


# Sync Composio connections into DB
@router.post("/connections/sync")
def sync_connections(user: dict = Depends(current_user)):
    """Sync active connections from Composio to our DB."""
    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    refresh_connections_from_composio(m["org_id"])
    active = get_org_connections(m["org_id"])
    return {"synced": True, "active_connections": len(active), "tools": [c["toolkit"] for c in active]}


# ======================================================================
# Workflow endpoints
# ======================================================================

# List workflow templates grouped by function
@router.get("/workflows")
def list_workflows(user: dict = Depends(current_user)):
    """List all available workflow templates grouped by function."""
    result = {}
    for func, wfs in WORKFLOWS.items():
        result[func] = [{"id": w["id"], "description": w["description"],
                          "tool_count": len(w.get("tools", [])), "risk": w["risk"]}
                        for w in wfs]
    return {"functions": len(result), "total_workflows": sum(len(w) for w in result.values()), "workflows": result}


# Suggest workflows matching a message
@router.post("/workflows/suggest")
def suggest_workflows(body: dict, user: dict = Depends(current_user)):
    """Suggest workflows matching a user message."""
    message = body.get("message", "")
    matches = match_workflows(message, max_results=3)
    return {"matches": [{"id": m["id"], "function": m["function"],
                          "description": m["description"],
                          "tool_count": len(m.get("tools", [])),
                          "expected_outcome": m["expected_outcome"],
                          "risk": m["risk"]} for m in matches]}


# Execute a workflow by id (owner-only)
@router.post("/workflows/execute")
def execute_workflow(body: dict, user: dict = Depends(current_user)):
    """Execute a workflow by ID. Owner-only."""
    if not mcp_enabled():
        raise HTTPException(503, "MCP disabled")
    if not is_connected():
        raise HTTPException(412, "No connected services")

    m = _active_membership(user)
    if not m:
        raise HTTPException(403, "Not in an organization")
    if m["role"] != "owner":
        raise HTTPException(403, "Only workspace owner")

    workflow_id = body.get("workflow_id", "")
    # Find the workflow
    workflow = None
    for func, wfs in WORKFLOWS.items():
        for w in wfs:
            if w["id"] == workflow_id:
                workflow = w
                break
        if workflow:
            break

    if not workflow:
        raise HTTPException(404, f"Workflow '{workflow_id}' not found")

    # Convert to execution plan
    plan = workflow_to_execution_plan(workflow)
    if not plan or not plan["actions"]:
        raise HTTPException(422, "Workflow has no executable actions")

    # Budget check
    if m and m.get("org_id"):
        try:
            from .bridge import enforce_budget
            if not enforce_budget(m["org_id"], 0):
                raise HTTPException(402, "Monthly execution budget exceeded")
        except Exception:
            pass

    result = execute_plan(plan, "general", org_id=m["org_id"] if m else None)

    return {
        "workflow": workflow_id,
        "description": workflow["description"],
        "execution_id": "exec_" + uuid.uuid4().hex[:16],
        "actions": result["actions"],
        "summary": result["summary"],
    }
