"""One error format for every endpoint:

    {"error": {"code": "not_found", "message": "...", "details": ...}}

The frontend only has to handle this one shape.
"""
import logging
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("rehlaguide.api")


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(message: str) -> APIError:
    return APIError(404, "not_found", message)


def bad_request(message: str) -> APIError:
    return APIError(400, "bad_request", message)


def from_agent_error(message: str) -> APIError:
    """Map the {"ok": False, "error": ...} strings from agents/ to an HTTP status."""
    lowered = message.lower()
    if "gemini_api_key" in lowered:
        return APIError(503, "llm_not_configured", "The language model is not configured on the server.")
    if "gemini call failed" in lowered or "empty response" in lowered or "valid json" in lowered:
        return APIError(502, "llm_unavailable", "The language model is temporarily unavailable. Please try again.", message)
    if "retrieval failed" in lowered or "malformed retriever" in lowered:
        return APIError(503, "retrieval_unavailable", "The attractions search index is unavailable.", message)
    if "must be a non-empty string" in lowered:
        return APIError(400, "bad_request", message)
    return APIError(502, "agent_error", "The travel agent could not complete the request.", message)


def _body(code: str, message: str, details: Optional[Any] = None) -> dict:
    error: dict = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.warning("%s: %s (%s)", exc.code, exc.message, exc.details)
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
                   for err in exc.errors()]
        return JSONResponse(status_code=422, content=_body("validation_error", "Invalid request.", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        return JSONResponse(status_code=exc.status_code, content=_body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error")
        return JSONResponse(status_code=500, content=_body("internal_error", "Unexpected server error."))
