"""Auth primitives shared by all routers (JWT, password hashing, admin gate).
Supports both sync and async endpoints. Tokens stored in DB — revocable server-side.
Auth via httpOnly cookie (primary) or Authorization header (fallback)."""
import os
import uuid
from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, Header, Depends, Request
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from db import users_col, async_users_col, sessions_col, async_sessions_col

import logging

_log = logging.getLogger("sdg")

# Password hashing, JWT secret, and cookie settings
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret")
if not JWT_SECRET or JWT_SECRET in ("dev-secret", "dev-jwt-secret", "dev-jwt-secret-change-in-production"):
    _log.warning("SECURITY WARNING: Using a weak/default JWT_SECRET. Set a strong random secret in production.")
    if JWT_SECRET.startswith("dev-"):
        _log.warning(f"  Current JWT_SECRET starts with 'dev-', suggesting it's a placeholder.")

TOKEN_DAYS = 30
COOKIE_NAME = "sdg_token"
_COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "").strip() or ".smartdecigen.com"
COOKIE_OPTIONS = {
    "httponly": True,
    "secure": os.environ.get("COOKIE_SECURE", "true").lower() in ("1", "true", "yes"),
    "samesite": "lax",
    "max_age": TOKEN_DAYS * 86400,
    "path": "/",
    "domain": _COOKIE_DOMAIN if _COOKIE_DOMAIN != "localhost" else None,
}


# Attach the session cookie to a response
def set_auth_cookie(response, jwt_str: str):
    response.set_cookie(COOKIE_NAME, jwt_str, **COOKIE_OPTIONS)


# Remove the session cookie from a response
def clear_auth_cookie(response):
    response.delete_cookie(COOKIE_NAME, path="/", domain=COOKIE_OPTIONS.get("domain"))


def _get_token(request: Request, authorization: str = Header(None)) -> str | None:
    """Read JWT from httpOnly cookie first, fallback to Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        return token
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1]
    return None


# Current UTC timestamp helper
def now_utc():
    return datetime.now(timezone.utc)


# Coerce naive datetimes to UTC-aware
def as_aware(dt):
    if dt and getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def make_token(user_id: str) -> tuple[str, str]:
    """Create a JWT + store session in DB. Returns (token_id, jwt_string)."""
    token_id = str(uuid.uuid4())
    exp = now_utc() + timedelta(days=TOKEN_DAYS)
    j = jwt.encode({"sub": user_id, "jti": token_id, "exp": exp}, JWT_SECRET, algorithm="HS256")
    sessions_col.insert_one({
        "token_id": token_id, "user_id": user_id,
        "created_at": now_utc(), "expires_at": exp, "revoked": False,
    })
    return token_id, j


# Revoke a single session token
def revoke_token(token_id: str):
    sessions_col.update_one({"token_id": token_id}, {"$set": {"revoked": True}})


def revoke_all_user_tokens(user_id: str):
    """Revoke every session for a user (e.g. password change, account ban)."""
    sessions_col.update_many({"user_id": user_id}, {"$set": {"revoked": True}})


# Decode and validate the JWT signature
def _decode_token(token: str | None) -> dict:
    if not token:
        raise HTTPException(401, "Not authenticated")
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        raise HTTPException(401, "Invalid or expired token")


# Ensure the session still exists and is not revoked
def _verify_session(payload: dict):
    token_id = payload.get("jti")
    if not token_id:
        raise HTTPException(401, "Token missing session id")
    session = sessions_col.find_one({"token_id": token_id})
    if not session or session.get("revoked"):
        raise HTTPException(401, "Session revoked or not found")


# Resolve the authenticated user for sync endpoints
def current_user(request: Request, authorization: str = Header(None)) -> dict:
    token = _get_token(request, authorization)
    payload = _decode_token(token)
    _verify_session(payload)
    user = users_col.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(401, "User not found")
    return user


# Resolve the authenticated user for async endpoints
async def current_user_async(request: Request, authorization: str = Header(None)) -> dict:
    token = _get_token(request, authorization)
    payload = _decode_token(token)
    token_id = payload.get("jti")
    if not token_id:
        raise HTTPException(401, "Token missing session id")
    session = await async_sessions_col.find_one({"token_id": token_id})
    if not session or session.get("revoked"):
        raise HTTPException(401, "Session revoked or not found")
    user = await async_users_col.find_one({"id": payload["sub"]})
    if not user:
        raise HTTPException(401, "User not found")
    return user


# Resolve the user if logged in, else None
def optional_user(request: Request, authorization: str = Header(None)):
    token = _get_token(request, authorization)
    if not token:
        return None
    try:
        payload = _decode_token(token)
        token_id = payload.get("jti")
        if not token_id:
            return None
        session = sessions_col.find_one({"token_id": token_id})
        if not session or session.get("revoked"):
            return None
        return users_col.find_one({"id": payload["sub"]})
    except Exception:
        return None


# Async version of optional_user
async def optional_user_async(request: Request, authorization: str = Header(None)):
    token = _get_token(request, authorization)
    if not token:
        return None
    try:
        payload = _decode_token(token)
        token_id = payload.get("jti")
        if not token_id:
            return None
        if async_sessions_col is None:
            return None
        session = await async_sessions_col.find_one({"token_id": token_id})
        if not session or session.get("revoked"):
            return None
        return await async_users_col.find_one({"id": payload["sub"]})
    except Exception:
        return None


# Cleanup job: delete expired sessions older than 60 days
def cleanup_expired_sessions():
    cutoff = now_utc() - timedelta(days=60)
    sessions_col.delete_many({"expires_at": {"$lt": cutoff}})


# Gate sync endpoints to admin users
def require_admin(user: dict = Depends(current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "Founder access only")
    return user


# Gate async endpoints to admin users
async def require_admin_async(user: dict = Depends(current_user_async)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "Founder access only")
    return user
