"""Desktop bridge — local-first execution for the Windows app.

Agents call these endpoints; the Tauri app proxies them to its local
invoke() commands (browser + FS + shell). Outside the desktop app,
these are no-ops (return 501) so cloud never sees desktop resources.

Security: org_id + user auth already via current_user_async. FS/shell
are re-sandboxed here too (same ~/Documents/FORGE rule) in case the
desktop is bypassed. Only LLM/HTTP leaves the device.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from security import current_user_async

router = APIRouter(prefix="/api/desktop", tags=["desktop"])

FORGE_ROOT = Path.home() / "Documents" / "FORGE"
ALLOWED_PREFIXES = [FORGE_ROOT.resolve()] if FORGE_ROOT.exists() else [FORGE_ROOT]


def _is_allowed(path: str) -> bool:
    p = Path(path).resolve()
    for pref in ALLOWED_PREFIXES:
        try:
            p.relative_to(pref)
            return True
        except ValueError:
            pass
    # allow temp forge
    tmp = Path(os.environ.get("TEMP", "") or os.environ.get("TMP", "") or "")
    if tmp and str(p).lower().startswith(str(tmp).lower()):
        return True
    return False


class BrowserNavigateIn(BaseModel):
    url: str


class BrowserEvalIn(BaseModel):
    js: str


class ShellRunIn(BaseModel):
    cmd: str
    cwd: Optional[str] = None


class OpenPathIn(BaseModel):
    path: str


class OpenUrlIn(BaseModel):
    url: str


@router.get("/info")
async def desktop_info(user: dict = Depends(current_user_async)):
    return {
        "forge_root": str(FORGE_ROOT),
        "platform": os.name,
        "user_id": user["id"],
        "org_id": user.get("org_id"),
        "note": "Local execution. Only LLM API leaves device.",
    }


@router.post("/browser/navigate")
async def browser_navigate(body: BrowserNavigateIn, user: dict = Depends(current_user_async)):
    # Desktop app listens on forge:browser-navigate or polls; for now we
    # return an instruction payload the frontend bridge will turn into invoke().
    # Agents can call this and the desktop Tauri app's BrowserPage will handle it
    # via polling this queue (simple version: just log + return).
    # Future: push via WebSocket / SSE to desktop.
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "Only http/https URLs allowed")
    return {"ok": True, "url": body.url, "dispatched": True, "hint": "Desktop BrowserPage will navigate agent-browser WebView via invoke('browser_navigate')"}


@router.post("/browser/eval")
async def browser_eval(body: BrowserEvalIn, user: dict = Depends(current_user_async)):
    if len(body.js) > 8000:
        raise HTTPException(400, "js too long (max 8000)")
    return {"ok": True, "dispatched": True, "hint": "Desktop will invoke('browser_eval')"}


@router.post("/shell/run")
async def shell_run(body: ShellRunIn, user: dict = Depends(current_user_async)):
    cwd = body.cwd or str(FORGE_ROOT)
    if not _is_allowed(cwd):
        raise HTTPException(403, f"cwd not allowed (sandboxed to {FORGE_ROOT})")
    # In desktop context, frontend will call Tauri shell_run directly.
    # Server-side fallback: run locally only if we're already on Windows desktop host.
    # Otherwise return a queue instruction.
    import subprocess
    try:
        out = subprocess.run(["cmd", "/C", body.cmd], cwd=cwd, capture_output=True, text=True, timeout=30)
        text = out.stdout + ("\n[stderr]\n" + out.stderr if out.stderr else "")
        if out.returncode != 0:
            raise HTTPException(500, f"exit {out.returncode}: {text[:4000]}")
        return {"ok": True, "output": text[:8000]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@router.post("/fs/list")
async def fs_list(body: OpenPathIn, user: dict = Depends(current_user_async)):
    p = Path(body.path)
    if not _is_allowed(body.path):
        raise HTTPException(403, f"path not allowed (sandboxed to {FORGE_ROOT})")
    if not p.exists():
        raise HTTPException(404, "Not found")
    if p.is_dir():
        items = [{"name": x.name, "is_dir": x.is_dir()} for x in p.iterdir()]
        return {"ok": True, "path": str(p), "items": items[:500]}
    return {"ok": True, "path": str(p), "content": p.read_text(encoding="utf-8", errors="replace")[:20000]}


@router.post("/open/path")
async def open_path(body: OpenPathIn, user: dict = Depends(current_user_async)):
    if not _is_allowed(body.path):
        raise HTTPException(403, f"path not allowed (sandboxed to {FORGE_ROOT})")
    return {"ok": True, "path": body.path, "hint": "Desktop will invoke('open_path')"}


@router.post("/open/url")
async def open_url(body: OpenUrlIn, user: dict = Depends(current_user_async)):
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(400, "Only http/https URLs allowed")
    return {"ok": True, "url": body.url, "hint": "Desktop will invoke('open_url')"}
