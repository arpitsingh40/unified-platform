"""Self-hosted MCP gateway — Composio v3 cloud + native Python handlers.
Tool definitions from memory/composio_catalog.json (1,403 toolkits).
Execution via Composio cloud API or native handler per service.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent.parent
load_dotenv(ROOT_DIR / '.env')

log = logging.getLogger("execution.mcp")

# Env flag to disable all MCP execution
DISABLE_MCP = os.environ.get("DISABLE_MCP", "").strip() in ("1", "true", "yes")

# ── Composio v3 SDK (cloud backend) ──
_composio_client = None
_composio_session = None
_mcp_url = None
_mcp_headers = None

# Lazily init Composio cloud client
def _composio_init():
    global _composio_client, _composio_session, _mcp_url, _mcp_headers
    if _composio_client is not None:
        return
    api_key = os.environ.get("COMPOSIO_API_KEY", "")
    if not api_key:
        _composio_client = False  # sentinel
        return
    try:
        from composio import Composio
        _composio_client = Composio()
        _composio_session = _composio_client.create(user_id="default")
        # ponytail: mcp endpoint is optional — session.execute() is the primary path
        mcp = getattr(_composio_session, "mcp", None)
        if mcp:
            _mcp_url = mcp.url
            _mcp_headers = mcp.headers
    except Exception as e:
        log.warning("Composio v3 init failed: %s", e)
        _composio_client = False
        _composio_session = None


# Low-level MCP JSON-RPC call helper
def _mcp_call(method: str, params: dict = None) -> dict:
    if _mcp_url is None:
        return {"error": "No MCP session", "successful": False}
    import httpx
    headers = {**_mcp_headers, "Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    body = {"jsonrpc": "2.0", "id": int(time.time() * 1000), "method": method}
    if params:
        body["params"] = params
    try:
        r = httpx.post(_mcp_url, headers=headers, json=body, timeout=60)
        text = r.text
        for block in text.split("\n\n"):
            data = ""
            for line in block.split("\n"):
                if line.startswith("data: "):
                    data += line[6:]
            if data:
                resp = json.loads(data)
                if "result" in resp:
                    res = resp["result"]
                    content = res.get("content", [])
                    if content and isinstance(content, list):
                        text_content = next((c["text"] for c in content if c.get("type") == "text"), "")
                        if res.get("isError") or "error" in text_content[:20]:
                            return {"error": text_content[:500], "successful": False}
                    return res
                if "error" in resp:
                    return {"error": resp["error"].get("message", str(resp["error"])), "successful": False}
        return {"error": f"Empty MCP response: {text[:200]}", "successful": False}
    except Exception as e:
        return {"error": str(e)[:300], "successful": False}


# Check whether MCP execution is available
def mcp_enabled() -> bool:
    if DISABLE_MCP:
        return False
    _composio_init()
    return True


def _get_native_handlers() -> dict:
    """Return {prefix: handler_fn} for native Python handlers."""
    from .handlers import registered_handlers
    return registered_handlers()


def _native_call(tool_name: str, arguments: dict) -> Optional[dict]:
    """Try native handler first. Returns result or None if no handler."""
    from .handlers import get_handler
    handler = get_handler(tool_name)
    if handler:
        return handler(tool_name, arguments)
    return None


# Execute tool via native handler or Composio
def call_tool(tool_name: str, arguments: dict, org_id: str = None) -> dict:
    if not mcp_enabled():
        return {"error": "MCP disabled", "successful": False, "execution_time_ms": 0}

    t0 = time.time()

    # 1. Try native handler first (faster, no cloud dependency)
    native_result = _native_call(tool_name, arguments)
    if native_result is not None:
        if "execution_time_ms" not in native_result:
            native_result["execution_time_ms"] = round((time.time() - t0) * 1000)
        return native_result

    # 2. Fall back to Composio cloud via session.execute
    _composio_init()
    if _composio_session and not isinstance(_composio_session, bool):
        try:
            result = _composio_session.execute(tool_name, arguments=arguments)
            elapsed = round((time.time() - t0) * 1000)
            resp = {"successful": True, "execution_time_ms": elapsed, "result": str(result)}
            if hasattr(result, "data"):
                resp["data"] = result.data
            return resp
        except Exception as e:
            err_msg = str(e)
            if hasattr(e, "body"):
                try:
                    err_msg = json.loads(e.body).get("error", {}).get("message", err_msg)
                except (json.JSONDecodeError, AttributeError, TypeError):
                    err_msg = str(e.body) if hasattr(e, "body") else err_msg
            elapsed = round((time.time() - t0) * 1000)
            # 3. Fall back to MCP tools/call
            result = _mcp_call("tools/call", {"name": tool_name, "arguments": arguments})
            if "error" not in result:
                result["execution_time_ms"] = elapsed
                result["successful"] = True
                return result
            return {"error": err_msg, "successful": False, "execution_time_ms": elapsed}

    # 3. Fall back to MCP tools/call
    result = _mcp_call("tools/call", {"name": tool_name, "arguments": arguments})
    elapsed = round((time.time() - t0) * 1000)
    if "error" not in result:
        result["execution_time_ms"] = elapsed
        result["successful"] = True
        return result

    return {"error": f"No handler or cloud access for {tool_name}", "successful": False, "execution_time_ms": elapsed}


# Check for any connected service credentials
def is_connected(org_id: str = None) -> bool:
    if not mcp_enabled():
        return False
    for key, val in os.environ.items():
        ukey = key.upper()
        if not val or ukey == "COMPOSIO_API_KEY":
            continue
        if ukey.endswith("_ACCESS_TOKEN") or ukey.endswith("_API_KEY") or ukey.endswith("_TOKEN"):
            return True
    if _composio_session and not isinstance(_composio_session, bool):
        return True
    return False


# Merge native and catalog tools into one list
def list_tools(refresh: bool = False, toolkit: str = None, org_id: str = None) -> list:
    if not mcp_enabled():
        return []

    from .catalog import list_tools as catalog_tools
    native_handlers = _get_native_handlers()

    if toolkit:
        return catalog_tools(toolkit=toolkit)

    # Merge native handler tools with catalog tools
    result = []
    seen = set()

    # Native handler tools (prioritized)
    for prefix, fn in native_handlers.items():
        if hasattr(fn, "tool_list"):
            for t in fn.tool_list:
                name = t.get("name", "")
                if name not in seen:
                    seen.add(name)
                    result.append(t)

    # Catalog tools: if we have a Composio session, surface ALL 1403 toolkits
    # ponytail: full catalog instead of per-env-var filtering — user has 1403 toolkits
    if _composio_session and not isinstance(_composio_session, bool):
        for t in catalog_tools():
            name = t.get("name", "")
            if name not in seen:
                seen.add(name)
                result.append(t)
    else:
        import os as _os
        configured = set()
        for key, val in _os.environ.items():
            if not val:
                continue
            ukey = key.upper()
            if ukey in ("COMPOSIO_API_KEY",):
                continue
            if ukey.endswith("_ACCESS_TOKEN"):
                configured.add(ukey.replace("_ACCESS_TOKEN", "").lower())
            elif ukey.endswith("_API_KEY"):
                configured.add(ukey.replace("_API_KEY", "").lower())
            elif ukey.endswith("_TOKEN"):
                prefix = ukey.replace("_TOKEN", "").lower()
                if not prefix.endswith("access") and not prefix.endswith("api"):
                    configured.add(prefix)
        for service in configured:
            if service in ("composio",):
                continue
            if service.upper() in native_handlers:
                continue
            tools = catalog_tools(toolkit=service, limit=30)
            for t in tools:
                name = t.get("name", "")
                if name not in seen:
                    seen.add(name)
                    result.append(t)

    return result


# Department to allowed toolkit prefixes map
DEPARTMENT_TOOL_SCOPE = {
    "sales": ["gmail", "hubspot", "linkedin", "calendar", "stripe"],
    "marketing": ["gmail", "linkedin", "twitter", "youtube", "notion"],
    "engineering": ["github", "gitlab", "vercel", "aws", "jira", "slack"],
    "product": ["github", "jira", "notion", "slack", "linear"],
    "operations": ["gmail", "notion", "jira", "slack", "calendar"],
    "finance": ["stripe", "quickbooks", "gmail", "sheets"],
    "leadership": [],
    "general": ["gmail", "calendar", "notion"],
}


# Filter tools by department scope
def tools_for_department(function: str, org_id: str = None) -> list:
    scope = DEPARTMENT_TOOL_SCOPE.get(function, [])
    if not scope:
        return list_tools()
    all_tools = list_tools()
    return [t for t in all_tools if any(t["name"].lower().startswith(prefix) for prefix in scope)]


# All tools for the founder
def tools_for_founder(org_id: str = None) -> list:
    return list_tools()


# List toolkits with active credentials
def linked_toolkits() -> list:
    linked = []
    seen = set()
    for key, val in os.environ.items():
        ukey = key.upper()
        if not val or ukey == "COMPOSIO_API_KEY":
            continue
        slug = None
        if ukey.endswith("_ACCESS_TOKEN"):
            slug = ukey.replace("_ACCESS_TOKEN", "").lower()
        elif ukey.endswith("_API_KEY"):
            slug = ukey.replace("_API_KEY", "").lower()
        elif ukey.endswith("_TOKEN"):
            slug = ukey.replace("_TOKEN", "").lower()
            if slug.endswith("access") or slug.endswith("api"):
                slug = None
        if slug and slug not in seen:
            seen.add(slug)
            linked.append({"toolkit": slug, "connections": 1})

    if _composio_session and not isinstance(_composio_session, bool):
        try:
            accounts = _composio_client.connected_accounts.list()
            for acc in accounts.items:
                slug = getattr(acc, "toolkit", None) or getattr(acc, "app", None) or getattr(acc, "app_name", None)
                if slug and slug not in seen:
                    seen.add(slug)
                    linked.append({"toolkit": slug, "connections": 1})
        except Exception:
            pass

    return linked


# Search catalog tools by query
def search_tools(query: str, limit: int = 10, org_id: str = None) -> list:
    if not mcp_enabled():
        return []
    from .catalog import search_tools as cat_search
    return cat_search(query, limit)
