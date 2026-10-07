"""GitHub handler — issues, repos via GitHub API."""

import os
import time
import logging
import httpx

from . import register

log = logging.getLogger("execution.handlers.github")

# GitHub tool definitions
TOOLS = [
    {"name": "GITHUB_CREATE_ISSUE", "description": "Create a GitHub issue", "inputSchema": {"repo": "string", "title": "string", "body": "string"}},
    {"name": "GITHUB_LIST_ISSUES", "description": "List GitHub issues", "inputSchema": {"repo": "string", "state": "string"}},
]


# Execute GitHub API tool call
@register("GITHUB")
def handle(tool_name: str, args: dict) -> dict:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return {"error": "GITHUB_TOKEN not configured", "successful": False}

    t0 = time.time()
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
    repo = args.get("repo", args.get("repository", os.environ.get("GITHUB_DEFAULT_REPO", "")))

    try:
        if tool_name == "GITHUB_CREATE_ISSUE":
            title, body_text = args.get("title", ""), args.get("body", "")
            if not title or not repo:
                return {"error": "Missing title or repo", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}
            r = httpx.post(f"https://api.github.com/repos/{repo}/issues", headers=headers, json={"title": title, "body": body_text}, timeout=30)
            if r.status_code in (200, 201):
                return {"result": f"Issue created: {r.json().get('html_url', '')}", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"GitHub API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

        if tool_name == "GITHUB_LIST_ISSUES":
            r = httpx.get(f"https://api.github.com/repos/{repo}/issues", headers=headers, params={"state": args.get("state", "open"), "per_page": args.get("per_page", 20)}, timeout=30)
            if r.status_code == 200:
                issues = r.json()
                lines = [f"- #{i['number']} {i['title']} ({i['state']})" for i in issues[:10]]
                return {"result": "\n".join(lines) if lines else "No issues found", "successful": True, "execution_time_ms": round((time.time()-t0)*1000)}
            return {"error": f"GitHub API {r.status_code}: {r.text[:200]}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

        return {"error": f"Unsupported GitHub tool: {tool_name}", "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

    except httpx.RequestError as e:
        return {"error": str(e)[:300], "successful": False, "execution_time_ms": round((time.time()-t0)*1000)}

handle.tool_list = TOOLS
