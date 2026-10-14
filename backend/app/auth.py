"""Sign-in for the deployed app: each person has an email and a password.

Accounts come from the APP_USERS environment variable (set in Vercel, never in code), as JSON:

    APP_USERS={"dhruv.gohil@thesleepcompany.in": "…", "ashish.kumar@thesleepcompany.in": "…"}

Leave APP_USERS empty for local use without a login. APP_SECRET signs the session cookie.

    POST /api/auth/login  {email, password}  → sets a signed session cookie (valid SESSION_DAYS)
    POST /api/auth/logout                    → clears it
    GET  /api/auth/status                    → {required, authenticated, email}

Every other /api route needs the cookie, except public report links (/api/reports/<token>/<file>), which
are meant to be shared. The cookie is "<email>|<issued unix time>|<HMAC-SHA256 signature>", signed with
APP_SECRET and that person's password: nothing to store server-side, removing someone from APP_USERS or
changing their password signs them out, and changing APP_SECRET signs everyone out.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.config import get_settings

log = logging.getLogger("auth")

COOKIE = "lz_session"
SESSION_DAYS = 30
PUBLIC_PATHS = ("/api/auth/", "/api/reports/")  # login itself, and shared report links
FAILED_LOGIN_DELAY_S = 1.0  # slows down password guessing

router = APIRouter(tags=["auth"])


def users() -> dict[str, str]:
    """{email (lower case): password} from APP_USERS. A malformed value means nobody can sign in."""
    raw = get_settings().app_users.strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {str(email).strip().lower(): str(pw) for email, pw in data.items()}
    except (ValueError, AttributeError):
        log.error('APP_USERS is not valid JSON like {"name@company.com": "password"}')
        return {"": ""}  # keeps sign-in required, but no one can match it


def auth_required() -> bool:
    return bool(get_settings().app_users.strip())


def _sign(email: str, issued: str, password: str) -> str:
    key = hashlib.sha256(f"{get_settings().app_secret}|{password}".encode()).digest()
    return hmac.new(key, f"{email}|{issued}".encode(), hashlib.sha256).hexdigest()


def make_token(email: str, now: float | None = None) -> str:
    issued = str(int(now if now is not None else time.time()))
    return f"{email}|{issued}|{_sign(email, issued, users()[email])}"


def signed_in_email(token: str | None, now: float | None = None) -> str | None:
    """The email in a valid, unexpired session cookie; None otherwise."""
    parts = (token or "").split("|")
    if len(parts) != 3 or not parts[1].isdigit():
        return None
    email, issued, sig = parts
    password = users().get(email)
    if password is None or not email or not hmac.compare_digest(sig, _sign(email, issued, password)):
        return None
    age = (now if now is not None else time.time()) - int(issued)
    return email if 0 <= age <= SESSION_DAYS * 86400 else None


class SignInGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path
        if (
            auth_required()
            and path.startswith("/api/")
            and not path.startswith(PUBLIC_PATHS)
            and not signed_in_email(request.cookies.get(COOKIE))
        ):
            return JSONResponse(
                {"error": {"code": "UNAUTHORIZED", "message": "Please sign in.", "detail": {}}},
                status_code=401,
            )
        return await call_next(request)


class LoginBody(BaseModel):
    email: str
    password: str


@router.get("/auth/status")
def status(request: Request) -> dict:
    email = signed_in_email(request.cookies.get(COOKIE))
    return {"required": auth_required(), "authenticated": email is not None, "email": email}


@router.post("/auth/login")
async def login(body: LoginBody, request: Request) -> Response:
    email = body.email.strip().lower()
    password = users().get(email)
    if not email or password is None or not hmac.compare_digest(body.password.encode(), password.encode()):
        await asyncio.sleep(FAILED_LOGIN_DELAY_S)
        return JSONResponse(
            {"error": {"code": "UNAUTHORIZED", "message": "Wrong email or password.", "detail": {}}},
            status_code=401,
        )
    res = JSONResponse({"ok": True, "email": email})
    res.set_cookie(
        COOKIE,
        make_token(email),
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
