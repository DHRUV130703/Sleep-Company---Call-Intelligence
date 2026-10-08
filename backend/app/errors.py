"""Error codes and the plain-language messages users see (PRD §6.2.2).

Raise `AppError(ErrorCode.X)` anywhere. The API turns it into:
    {"error": {"code": "X", "message": "...", "detail": {...}}}
Stack traces never reach the UI.
"""

import logging
from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger(__name__)


class ErrorCode(StrEnum):
    # Pipeline (shown on the Batch progress page)
    LINK_NOT_FOUND = "LINK_NOT_FOUND"
    LINK_FORBIDDEN = "LINK_FORBIDDEN"
    LINK_UNREACHABLE = "LINK_UNREACHABLE"
    LINK_INVALID = "LINK_INVALID"
    LINK_BLOCKED = "LINK_BLOCKED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    NOT_AUDIO = "NOT_AUDIO"
    TOO_SHORT = "TOO_SHORT"
    SILENT = "SILENT"
    NOT_CONNECTED = "NOT_CONNECTED"
    CANCELLED = "CANCELLED"
    TOO_LONG = "TOO_LONG"
    PROVIDER_RATE_LIMIT = "PROVIDER_RATE_LIMIT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_NOT_CONFIGURED = "PROVIDER_NOT_CONFIGURED"
    PROVIDER_NO_CREDITS = "PROVIDER_NO_CREDITS"
    ANALYSIS_INVALID = "ANALYSIS_INVALID"
    # API
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIG_INVALID = "CONFIG_INVALID"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UPLOAD_INCOMPLETE = "UPLOAD_INCOMPLETE"
    UPLOAD_CORRUPT = "UPLOAD_CORRUPT"
    BAD_ARCHIVE = "BAD_ARCHIVE"
    BAD_SHEET = "BAD_SHEET"
    TOO_MANY_CALLS = "TOO_MANY_CALLS"
    NOTHING_TO_PROCESS = "NOTHING_TO_PROCESS"
    NOT_ENOUGH_DATA = "NOT_ENOUGH_DATA"


MESSAGES: dict[ErrorCode, str] = {
    ErrorCode.LINK_NOT_FOUND: "The recording was not found (HTTP 404). Check the link.",
    ErrorCode.LINK_FORBIDDEN: "Access denied (HTTP 403). The link may have expired or need sign-in.",
    ErrorCode.LINK_UNREACHABLE: "Couldn't reach the server hosting this recording.",
    ErrorCode.LINK_INVALID: "This isn't a valid http(s) link.",
    ErrorCode.LINK_BLOCKED: "Links to private or local network addresses are blocked for safety.",
    ErrorCode.FILE_TOO_LARGE: "This file is larger than the allowed maximum.",
    ErrorCode.NOT_AUDIO: "This file isn't an audio or video recording.",
    ErrorCode.TOO_SHORT: "Call shorter than 5 seconds. Marked as not connected.",
    ErrorCode.SILENT: "No speech detected.",
    ErrorCode.NOT_CONNECTED: "Only one side spoke. Counted as not connected.",
    ErrorCode.CANCELLED: "Cancelled.",
    ErrorCode.TOO_LONG: "This recording is longer than the allowed maximum.",
    ErrorCode.PROVIDER_RATE_LIMIT: "The AI service is busy. Retrying automatically…",
    ErrorCode.PROVIDER_ERROR: "The AI service failed for this call.",
    ErrorCode.PROVIDER_NOT_CONFIGURED: "No API key is set for the selected provider. Add it to .env.",
    ErrorCode.PROVIDER_NO_CREDITS: "The AI service can't be used right now.",
    ErrorCode.ANALYSIS_INVALID: "Analysis couldn't be completed for this call.",
    ErrorCode.NOT_FOUND: "Not found.",
    ErrorCode.VALIDATION_ERROR: "Some of the information sent is invalid.",
    ErrorCode.CONFIG_INVALID: "A config file has a mistake.",
    ErrorCode.INTERNAL_ERROR: "Something went wrong on our side.",
    ErrorCode.UPLOAD_INCOMPLETE: "Some parts of the file haven't been uploaded yet.",
    ErrorCode.UPLOAD_CORRUPT: "The uploaded file didn't arrive intact. Please upload it again.",
    ErrorCode.BAD_ARCHIVE: "This ZIP file can't be opened or is unsafe.",
    ErrorCode.BAD_SHEET: "This spreadsheet can't be read. Save it as .xlsx or .csv and try again.",
    ErrorCode.TOO_MANY_CALLS: "Too many calls in one batch.",
    ErrorCode.NOTHING_TO_PROCESS: "No recordings were found to process.",
    ErrorCode.NOT_ENOUGH_DATA: "Not enough analysed calls on both sides to compare yet.",
}

HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.CONFIG_INVALID: 422,
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    def __init__(self, code: ErrorCode, message: str | None = None, detail: dict[str, Any] | None = None):
        self.code = code
        self.message = message or MESSAGES[code]
        self.detail = detail or {}
        super().__init__(f"{code}: {self.message}")

    @property
    def http_status(self) -> int:
        return HTTP_STATUS.get(self.code, 400)


def _body(code: ErrorCode, message: str, detail: dict[str, Any] | None = None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail or {}}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(_body(exc.code, exc.message, exc.detail), status_code=exc.http_status)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else ErrorCode.VALIDATION_ERROR
        if exc.status_code >= 500:
            code = ErrorCode.INTERNAL_ERROR
        message = MESSAGES[code] if exc.status_code in (404, 500) else str(exc.detail)
        return JSONResponse(_body(code, message), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        detail = {"fields": [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]}
        return JSONResponse(
            _body(ErrorCode.VALIDATION_ERROR, MESSAGES[ErrorCode.VALIDATION_ERROR], detail), status_code=422
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            _body(ErrorCode.INTERNAL_ERROR, MESSAGES[ErrorCode.INTERNAL_ERROR]), status_code=500
        )
