"""Gmail handler — send/search emails via Gmail API."""

import os
import time
import base64
import logging
import httpx

from . import register

log = logging.getLogger("execution.handlers.gmail")

# Gmail tool definitions
TOOLS = [
    {"name": "GMAIL_SEND_EMAIL", "description": "Send an email via Gmail", "inputSchema": {"to": "string", "subject": "string", "body": "string"}},
    {"name": "GMAIL_SEARCH_MESSAGES", "description": "Search Gmail inbox", "inputSchema": {"query": "string", "max_results": "integer"}},
]


# Execute Gmail API tool call
@register("GMAIL")
def handle(tool_name: str, args: dict) -> dict:
    token = os.environ.get("GMAIL_ACCESS_TOKEN", "")
    if not token:
        return {"error": "GMAIL_ACCESS_TOKEN not configured", "successful": False}

    t0 = time.time()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    try:
        if tool_name == "GMAIL_SEND_EMAIL":
            to = args.get("to", args.get("recipient", ""))
            subject = args.get("subject", "")
            body = args.get("body", args.get("message", ""))
            if not to:
                return {"error": "Missing recipient (to)", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
            msg = f"To: {to}\r\nSubject: {subject}\r\n\r\n{body}"
            encoded = base64.urlsafe_b64encode(msg.encode()).decode()
            r = httpx.post("https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                              headers=headers, json={"raw": encoded}, timeout=30)
            if r.status_code == 200:
                data = r.json()
                return {"result": f"Email sent to {to}, id={data.get('id','')}", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Gmail API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

        if tool_name == "GMAIL_SEARCH_MESSAGES":
            r = httpx.get("https://gmail.googleapis.com/gmail/v1/users/me/messages",
                             headers=headers, params={"q": args.get("query", ""), "maxResults": args.get("max_results", 10)}, timeout=30)
            if r.status_code == 200:
                msgs = r.json().get("messages", [])
                return {"result": f"Found {len(msgs)} messages", "successful": True, "data": msgs, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Gmail API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

        return {"error": f"Unsupported Gmail tool: {tool_name}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

    except httpx.RequestError as e:
        return {"error": str(e)[:300], "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

handle.tool_list = TOOLS
