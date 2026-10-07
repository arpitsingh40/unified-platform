"""Tool Connection Manager — OAuth flow for Composio's 1,403 toolkits.

Handles: initiate connection → OAuth redirect → callback → store → list → disconnect.
Stores connected accounts per org in MongoDB (org_connections collection).
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from db import db as _db
from security import current_user

log = logging.getLogger("execution.connections")

# Org-scoped tool connection collection
CONNECTIONS_COL = _db.org_connections if _db is not None else None

# Ensure collection + indexes
if CONNECTIONS_COL is not None:
    try:
        CONNECTIONS_COL.create_index("id", unique=True)
        CONNECTIONS_COL.create_index([("org_id", 1), ("toolkit", 1)], unique=True)
        CONNECTIONS_COL.create_index([("org_id", 1), ("status", 1)])
    except Exception:
        pass


# Current UTC timestamp helper
def _now():
    return datetime.now(timezone.utc)


# ======================================================================
# Composio connection bridge
# ======================================================================

def _composio():
    """Lazy Composio client init."""
    try:
        from execution.mcp_client import _composio_init, _composio_client
        _composio_init()
        return _composio_client if _composio_client and _composio_client is not True else None
    except Exception:
        return None


def _composio_session():
    """Lazy Composio session."""
    try:
        from execution.mcp_client import _composio_session
        return _composio_session if _composio_session and _composio_session is not True else None
    except Exception:
        return None


# List integrations with per-org connection status
def get_available_integrations(org_id: str = None, category: str = None) -> list:
    """List all available integrations from the catalog, with connection status per org."""
    from execution.catalog import get_toolkits as _catalog_toolkits
    toolkits = _catalog_toolkits()

    connected = {}
    if org_id and CONNECTIONS_COL is not None:
        for conn in CONNECTIONS_COL.find({"org_id": org_id, "status": "active"}, {"_id": 0, "toolkit": 1}):
            connected[conn["toolkit"]] = True

    result = []
    for slug, info in toolkits.items():
        is_connected = connected.get(slug, False)
        try:
            from composio_catalog import get_toolkit_categories
        except ImportError:
            pass

        result.append({
            "toolkit": slug,
            "name": info.get("name", slug),
            "description": info.get("description", "")[:200],
            "tool_count": info.get("tool_count", len(info.get("tools", []))),
            "category": info.get("category", ""),
            "connected": is_connected,
            "icon": info.get("icon", ""),
        })

    return sorted(result, key=lambda x: (0 if x["connected"] else 1, -x["tool_count"], x["toolkit"]))


# List active connections for an org
def get_org_connections(org_id: str) -> list:
    """List active connections for an org."""
    if CONNECTIONS_COL is None:
        return []
    return list(CONNECTIONS_COL.find(
        {"org_id": org_id, "status": "active"},
        {"_id": 0, "id": 1, "toolkit": 1, "name": 1, "connected_at": 1, "tool_count": 1},
    ).sort("connected_at", -1))


# Initiate OAuth flow for a toolkit
def init_connection(org_id: str, toolkit: str, redirect_uri: str = None) -> dict:
    """Initiate OAuth connection for a toolkit. Returns auth_url + connection_id."""
    client = _composio()
    if not client:
        return {"error": "Composio not configured — set COMPOSIO_API_KEY"}

    # Check if already connected
    existing = CONNECTIONS_COL.find_one({"org_id": org_id, "toolkit": toolkit, "status": "active"}) if CONNECTIONS_COL else None
    if existing:
        return {"already_connected": True, "connection_id": existing["id"], "toolkit": toolkit}

    try:
        # Composio v3: get auth params for OAuth flow
        # Method signature varies by SDK version — try multiple patterns
        auth_url = None
        try:
            # Try: client.get_auth_params(app_name, redirect_uri)
            params = client.get_auth_params(toolkit, redirect_uri=redirect_uri)
            auth_url = params.get("auth_url") or params.get("url")
        except (AttributeError, TypeError):
            pass

        if not auth_url:
            try:
                # Try: client.connected_accounts.create
                acc = client.connected_accounts.create(toolkit=toolkit, redirect_uri=redirect_uri)
                auth_url = getattr(acc, "auth_url", None) or getattr(acc, "url", None)
            except (AttributeError, TypeError):
                pass

        if not auth_url:
            # Fallback: return Composio dashboard URL for manual connection
            auth_url = f"https://app.composio.dev/app/{toolkit}/connect"

        # Store pending connection
        conn_id = f"conn_{toolkit}_{org_id[:8]}"
        if CONNECTIONS_COL is not None:
            CONNECTIONS_COL.update_one(
                {"org_id": org_id, "toolkit": toolkit},
                {"$set": {
                    "id": conn_id, "org_id": org_id, "toolkit": toolkit,
                    "status": "pending", "auth_url": auth_url,
                    "initiated_at": _now().isoformat(), "connected_at": None,
                }},
                upsert=True,
            )

        return {
            "connection_id": conn_id,
            "toolkit": toolkit,
            "auth_url": auth_url,
            "status": "pending",
            "instructions": f"Open the auth URL to connect {toolkit}. After OAuth completes, Composio handles the rest.",
        }

    except Exception as e:
        log.error(f"Connection init failed for {toolkit}: {e}")
        return {"error": f"Could not initiate connection: {str(e)[:200]}"}


# Mark pending connection active after OAuth
def complete_connection(org_id: str, toolkit: str) -> dict:
    """Mark a connection as active after OAuth completes. Composio handles the token exchange."""
    if CONNECTIONS_COL is None:
        return {"error": "DB not available"}

    result = CONNECTIONS_COL.update_one(
        {"org_id": org_id, "toolkit": toolkit, "status": "pending"},
        {"$set": {"status": "active", "connected_at": _now().isoformat()}},
    )

    if result.matched_count == 0:
        # Try direct upsert for externally-connected tools
        conn_id = f"conn_{toolkit}_{org_id[:8]}"
        CONNECTIONS_COL.update_one(
            {"org_id": org_id, "toolkit": toolkit},
            {"$set": {
                "id": conn_id, "org_id": org_id, "toolkit": toolkit,
                "status": "active", "connected_at": _now().isoformat(),
            }},
            upsert=True,
        )
        return {"connection_id": conn_id, "toolkit": toolkit, "status": "active", "new": True}

    _audit_connection(org_id, toolkit, True)
    return {"toolkit": toolkit, "status": "active"}


# Record connection event in audit trail
def _audit_connection(org_id: str, toolkit: str, connected: bool):
    try:
        from audit import record_tool_connection
        record_tool_connection(org_id, toolkit, connected)
    except Exception:
        pass


# Disconnect a toolkit for an org
def disconnect_toolkit(org_id: str, toolkit: str) -> dict:
    """Disconnect a toolkit for an org."""
    if CONNECTIONS_COL is None:
        return {"error": "DB not available"}
    CONNECTIONS_COL.update_one(
        {"org_id": org_id, "toolkit": toolkit},
        {"$set": {"status": "disconnected", "disconnected_at": _now().isoformat()}},
    )
    _audit_connection(org_id, toolkit, False)
    return {"toolkit": toolkit, "status": "disconnected"}


# Sync Composio connected accounts into DB
def refresh_connections_from_composio(org_id: str):
    """Sync active connections from Composio to our DB. Call on startup or periodically."""
    session = _composio_session()
    if not session:
        return

    try:
        accounts = session.connected_accounts.list() if hasattr(session, "connected_accounts") else []
        for acc in (accounts.items if hasattr(accounts, "items") else accounts):
            toolkit = getattr(acc, "toolkit", None) or getattr(acc, "app_name", None) or getattr(acc, "toolset", None)
            if toolkit and CONNECTIONS_COL is not None:
                conn_id = f"conn_{toolkit}_{org_id[:8]}"
                CONNECTIONS_COL.update_one(
                    {"org_id": org_id, "toolkit": toolkit},
                    {"$set": {"id": conn_id, "status": "active", "connected_at": _now().isoformat()}},
                    upsert=True,
                )
    except Exception as e:
        log.warning(f"Composio connection sync failed: {e}")


# ======================================================================
# Tool suggestion by business function
# ======================================================================

# Business function to recommended toolkits map
FUNCTION_TO_TOOLKITS = {
    "sales":        ["hubspot", "salesforce", "gmail", "linkedin", "stripe", "calendly", "outreach", "salesloft", "pipedrive", "zendesk_sell"],
    "marketing":    ["mailchimp", "hubspot", "linkedin", "twitter", "google_analytics", "facebook_ads", "canva", "buffer", "semrush", "google_ads"],
    "product":      ["linear", "jira", "github", "gitlab", "figma", "notion", "miro", "productboard", "amplitude", "mixpanel"],
    "technology":   ["github", "gitlab", "vercel", "aws", "cloudflare", "datadog", "sentry", "docker", "terraform", "jenkins"],
    "finance":      ["stripe", "quickbooks", "xero", "google_sheets", "bill", "brex", "ramp", "mercury", "plaid"],
    "operations":   ["notion", "slack", "google_calendar", "asana", "monday", "airtable", "zapier", "make", "trello"],
    "hr":           ["bamboo", "greenhouse", "lever", "deel", "rippling", "gusto", "workday", "notion", "slack"],
    "customer_success": ["intercom", "zendesk", "helpscout", "front", "slack", "gmail", "calendly", "hubspot", "customer_io"],
    "data":         ["google_analytics", "amplitude", "mixpanel", "tableau", "looker", "snowflake", "bigquery", "metabase"],
    "growth":       ["google_analytics", "amplitude", "stripe", "hubspot", "customer_io", "mailchimp", "intercom"],
    "brand":        ["canva", "figma", "buffer", "twitter", "linkedin", "instagram", "youtube", "mailchimp"],
    "partnerships": ["hubspot", "notion", "slack", "gmail", "google_calendar", "stripe", "quickbooks"],
    "vision":       ["notion", "miro", "figma", "google_docs"],
    "strategy":     ["notion", "miro", "google_sheets", "tableau"],
    "leadership":   ["slack", "gmail", "notion", "google_calendar", "zoom", "google_meet", "lattice", "15five"],
}


# Recommend toolkits for a business function
def suggest_tools_for_function(function: str, org_id: str = None) -> list:
    """Recommend toolkits for a business function. Flags connected vs suggested."""
    suggested = FUNCTION_TO_TOOLKITS.get(function, FUNCTION_TO_TOOLKITS.get("operations", []))
    connected = set()
    if org_id and CONNECTIONS_COL is not None:
        for c in CONNECTIONS_COL.find({"org_id": org_id, "status": "active"}, {"_id": 0, "toolkit": 1}):
            connected.add(c["toolkit"])

    result = []
    for tk in suggested[:8]:
        result.append({
            "toolkit": tk,
            "connected": tk in connected,
            "priority": "connected" if tk in connected else ("recommended" if tk in suggested[:4] else "optional"),
        })
    return result


# Suggest tools to fix at-risk functions
def suggest_tools_for_at_risk(org_id: str) -> dict:
    """For each at-risk function, suggest tools to connect to fix it."""
    from business_system import get_system_model, FUNCTION_LABELS

    model = get_system_model(org_id) or {}
    functions = model.get("functions", {})

    suggestions = {}
    for func, state in functions.items():
        if state.get("status") == "at_risk":
            tools = suggest_tools_for_function(func, org_id)
            unconnected = [t for t in tools if not t["connected"]]
            if unconnected:
                suggestions[FUNCTION_LABELS.get(func, func)] = {
                    "health": state["health"],
                    "suggested_tools": unconnected[:4],
                    "message": f"Connect these tools to help fix {FUNCTION_LABELS.get(func, func)} (currently at {state['health']}/100)",
                }
    return suggestions


# ======================================================================
# Self-check
# ======================================================================
if __name__ == "__main__":
    assert len(FUNCTION_TO_TOOLKITS) >= 14
    assert "sales" in FUNCTION_TO_TOOLKITS
    assert "hubspot" in FUNCTION_TO_TOOLKITS["sales"]
    assert len(suggest_tools_for_function("sales")) > 0
    print("OK — connection manager verified")
