import os, time, logging, requests
from . import register
log = logging.getLogger("execution.handlers.stripe")
# Stripe tool definitions
TOOLS = [
    {"name": "STRIPE_LIST_INVOICES", "description": "List recent Stripe invoices", "inputSchema": {"limit": "integer"}},
]
# Execute Stripe API tool call
@register("STRIPE")
def handle(tool_name: str, args: dict) -> dict:
    key = os.environ.get("STRIPE_API_KEY", "")
    if not key:
        return {"error": "STRIPE_API_KEY not configured", "successful": False}
    t0 = time.time()
    try:
        if tool_name == "STRIPE_LIST_INVOICES":
            r = requests.get("https://api.stripe.com/v1/invoices", auth=(key, ""), params={"limit": min(args.get("limit", 10), 100)}, timeout=30)
            if r.status_code == 200:
                invs = r.json().get("data", [])
                lines = [f"- {i.get('number','?')}: ${i.get('amount_due',0)/100:.0f} ({i.get('status','')})" for i in invs[:10]]
                return {"result": "\n".join(lines) if lines else "No invoices", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"Stripe API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
        return {"error": f"Unsupported Stripe tool: {tool_name}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
    except requests.RequestException as e:
        return {"error": str(e)[:300], "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
handle.tool_list = TOOLS
