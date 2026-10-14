"""Team password for the deployed app. Set APP_PASSCODE (and APP_SECRET) in the environment to turn it on;
leave APP_PASSCODE empty for local use without a login.

    POST /api/auth/login  {password}  → sets a signed session cookie (valid SESSION_DAYS)
    POST /api/auth/logout             → clears it
    GET  /api/auth/status             → {required, authenticated}

Every other /api route needs the cookie, except public report links (/api/reports/<token>/<file>), which
are meant to be shared. The cookie is "<issued unix time>.<HMAC-SHA256 signature>": nothing to store
server-side, and changing APP_SECRET or APP_PASSCODE signs everyone out.
"""

import asyncio
import hashlib
import hmac
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

COOKIE = "lz_session"
SESSION_DAYS = 30
PUBLIC_PATHS = ("/api/auth/", "/api/reports/")  # login itself, and shared report links
FAILED_LOGIN_DELAY_S = 1.0  # slows down password guessing

router = APIRouter(tags=["auth"])


def auth_required() -> bool:
    return bool(get_settings().app_passcode)


def _key() -> bytes:
    s = get_settings()
    return hashlib.sha256(f"{s.app_secret}|{s.app_passcode}".encode()).digest()


def make_token(now: float | None = None) -> str:
    issued = str(int(now if now is not None else time.time()))
    sig = hmac.new(_key(), issued.encode(), hashlib.sha256).hexdigest()
    return f"{issued}.{sig}"


def token_valid(token: str | None, now: float | None = None) -> bool:
    if not token or "." not in token:
        return False
    issued, sig = token.split(".", 1)
    expected = hmac.new(_key(), issued.encode(), hashlib.sha256).hexdigest()
    if not issued.isdigit() or not hmac.compare_digest(sig, expected):
        return False
    age = (now if now is not None else time.time()) - int(issued)
    return 0 <= age <= SESSION_DAYS * 86400


class PasswordGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if (
            auth_required()
            and path.startswith("/api/")
            and not path.startswith(PUBLIC_PATHS)
            and not token_valid(request.cookies.get(COOKIE))
        ):
            return JSONResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "Please sign in.", "detail": {}}},
                status_code=401,
            )
        return await call_next(request)


class LoginBody(BaseModel):
    password: str


@router.get("/auth/status")
def status(request: Request) -> dict:
    return {"required": auth_required(), "authenticated": token_valid(request.cookies.get(COOKIE))}


@router.post("/auth/login")
async def login(body: LoginBody, request: Request) -> Response:
    password = get_settings().app_passcode
    if not password or not hmac.compare_digest(body.password.encode(), password.encode()):
        await asyncio.sleep(FAILED_LOGIN_DELAY_S)
        return JSONResponse(
            {"error": {"code": "UNAUTHORIZED", "message": "Wrong password.", "detail": {}}}, status_code=401
        )
    res = JSONResponse({"ok": True})
    res.set_cookie(
        COOKIE,
        make_token(),
        max_age=SESSION_DAYS * 86400,
        httponly=True,  # not readable by page scripts
        secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
        samesite="lax",
    )
    return res


@router.post("/auth/logout")
def logout() -> Response:
    res = JSONResponse({"ok": True})
    res.delete_cookie(COOKIE)
    return res
