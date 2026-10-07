import os, time, logging, requests
from . import register
log = logging.getLogger("execution.handlers.slack")
# Slack tool definitions
TOOLS = [
    {"name": "SLACK_SEND_MESSAGE", "description": "Send a Slack message", "inputSchema": {"channel": "string", "text": "string"}},
    {"name": "SLACK_LIST_CONVERSATIONS", "description": "List Slack channels", "inputSchema": {"limit": "integer"}},
]
# Execute Slack API tool call
@register("SLACK")
def handle(tool_name: str, args: dict) -> dict:
    token = os.environ.get("SLACK_TOKEN", "")
    if not token:
        return {"error": "SLACK_TOKEN not configured", "successful": False}
    t0 = time.time()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    try:
        if tool_name == "SLACK_SEND_MESSAGE":
            channel, text = args.get("channel", ""), args.get("text", args.get("message", ""))
            if not channel or not text:
                return {"error": "Missing channel or text", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
            r = requests.post("https://slack.com/api/chat.postMessage", headers=headers, json={"channel": channel, "text": text}, timeout=30)
            data = r.json()
            if data.get("ok"):
                return {"result": f"Message sent to {channel}", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Slack API: {data.get('error', 'unknown')}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
        if tool_name == "SLACK_LIST_CONVERSATIONS":
            r = requests.get("https://slack.com/api/conversations.list", headers=headers, params={"limit": args.get("limit", 20), "exclude_archived": True}, timeout=30)
            data = r.json()
            if data.get("ok"):
                channels = [f"#{c['name']}" for c in data.get("channels", [])[:10]]
                return {"result": "\n".join(channels) if channels else "No channels", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Slack API: {data.get('error', 'unknown')}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
        return {"error": f"Unsupported Slack tool: {tool_name}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
    except requests.RequestException as e:
        return {"error": str(e)[:300], "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
handle.tool_list = TOOLS
