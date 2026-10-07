"""Traffic tracking: visitor sessions with IP -> city/country and time spent.
Scale notes: NO per-request middleware (no write amplification). One session doc per
visit, updated by a 60s frontend heartbeat. Geo lookups hit ip-api.com at most ONCE
per unique IP ever (permanent geo_cache collection)."""
import uuid
import ipaddress
import logging
from typing import Optional
import requests as http
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from pymongo import ReturnDocument
from db import traffic_col, geo_col, users_col
from security import optional_user, now_utc, as_aware
from ledger import inc_stats

router = APIRouter(prefix="/api/track", tags=["tracking"])
log = logging.getLogger("tracking")


# Extract real client IP from proxy headers
def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


# Check if IP is private or loopback
def _is_private(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback
    except Exception:
        return True


def geo_lookup(ip: str) -> dict:
    """city/country for an IP. Cached forever per IP; free ip-api.com; 3s budget."""
    if not ip or _is_private(ip):
        return {"city": "Local", "country": "Local", "country_code": ""}
    cached = geo_col.find_one({"ip": ip})
    if cached:
        return {"city": cached.get("city", "Unknown"), "country": cached.get("country", "Unknown"),
                "country_code": cached.get("country_code", "")}
    doc = {"city": "Unknown", "country": "Unknown", "country_code": ""}
    try:
        r = http.get(f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,city", timeout=3)
        d = r.json()
        if d.get("status") == "success":
            doc = {"city": d.get("city", "Unknown"), "country": d.get("country", "Unknown"),
                   "country_code": d.get("countryCode", "")}
    except Exception as e:
        log.warning(f"geo lookup failed for {ip}: {e}")
    try:
        res = geo_col.update_one({"ip": ip}, {"$setOnInsert": {**doc, "ip": ip, "first_seen": now_utc()}}, upsert=True)
        if res.upserted_id is not None:
            inc_stats({"unique_ips": 1})
    except Exception:
        pass
    return doc


# Request body for session heartbeat
class SessionIn(BaseModel):
    session_id: Optional[str] = None


@router.post("/session")
def track_session(body: SessionIn, request: Request, user: Optional[dict] = Depends(optional_user)):
    """Create or heartbeat a visitor session. Frontend calls on load + every 60s."""
    now = now_utc()
    user_fields = {}
    if user:
        user_fields = {"user_id": user["id"], "user_email": user["email"]}
        users_col.update_one({"id": user["id"]}, {"$set": {"last_active_at": now}})
    if body.session_id:
        doc = traffic_col.find_one_and_update(
            {"session_id": body.session_id},
            {"$set": {"last_seen_at": now, **user_fields}, "$inc": {"beats": 1}},
            return_document=ReturnDocument.AFTER)
        if doc:
            dur = int((now - as_aware(doc["started_at"])).total_seconds())
            traffic_col.update_one({"session_id": body.session_id}, {"$set": {"duration_s": dur}})
            return {"session_id": body.session_id}
    ip = client_ip(request)
    geo = geo_lookup(ip)
    sid = str(uuid.uuid4())
    traffic_col.insert_one({
        "session_id": sid, "ip": ip, "city": geo["city"], "country": geo["country"],
        "country_code": geo["country_code"], "started_at": now, "last_seen_at": now,
        "duration_s": 0, "beats": 1, **user_fields,
    })
    inc_stats({"sessions_total": 1})
    if user and not user.get("country"):
        users_col.update_one({"id": user["id"]}, {"$set": {"country": geo["country"], "city": geo["city"], "last_ip": ip}})
    return {"session_id": sid}
