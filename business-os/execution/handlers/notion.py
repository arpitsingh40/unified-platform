import os, time, logging, requests
from . import register
log = logging.getLogger("execution.handlers.notion")
# Notion tool definitions
TOOLS = [
    {"name": "NOTION_CREATE_PAGE", "description": "Create a Notion page", "inputSchema": {"parent_id": "string", "title": "string"}},
]
# Execute Notion API tool call
@register("NOTION")
def handle(tool_name: str, args: dict) -> dict:
    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        return {"error": "NOTION_TOKEN not configured", "successful": False}
    t0 = time.time()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    try:
        if tool_name == "NOTION_CREATE_PAGE":
            parent_id, title = args.get("parent_id", args.get("database_id", "")), args.get("title", "")
            if not parent_id or not title:
                return {"error": "Missing parent_id or title", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
            r = requests.post("https://api.notion.com/v1/pages", headers=headers, json={"parent": {"database_id": parent_id}, "properties": {"title": {"title": [{"text": {"content": title}}]}}}, timeout=30)
            if r.status_code in (200, 201):
                return {"result": f"Page created: {r.json().get('url', '')}", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Notion API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
        return {"error": f"Unsupported Notion tool: {tool_name}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
    except requests.RequestException as e:
        return {"error": str(e)[:300], "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
handle.tool_list = TOOLS
