"""Định dạng phản hồi chung theo docs/07: {"data", "meta"} khi thành công, {"error"} khi lỗi."""
from __future__ import annotations

import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

HTTP_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
              409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 422: "VALIDATION_ERROR", 429: "RATE_LIMITED"}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: list | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or []


def not_found(message: str = "Không tìm thấy hoặc bạn không có quyền xem.") -> AppError:
    return AppError(404, "NOT_FOUND", message)


def forbidden(message: str = "Bạn không có quyền thực hiện thao tác này.") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def meta() -> dict:
    return {"request_id": request_id_var.get(), "timestamp": datetime.now(timezone.utc).isoformat()}


def ok(data: Any, status: int = 200, extra_meta: dict | None = None) -> JSONResponse:
    return JSONResponse({"data": jsonable_encoder(data), "meta": {**meta(), **(extra_meta or {})}}, status_code=status)


def _error(status: int, code: str, message: str, details: list | None = None) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message, "details": details or [],
                                   "request_id": request_id_var.get()}}, status_code=status)


def install(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_id(request: Request, call_next):
        rid = str(uuid.uuid4())
        request_id_var.set(rid)
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(AppError)
    async def app_error(_: Request, exc: AppError):
        return _error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return _error(422, "VALIDATION_ERROR", "Dữ liệu không hợp lệ.", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, HTTP_CODES.get(exc.status_code, "ERROR"), str(exc.detail))

    @app.exception_handler(Exception)
    async def server_error(_: Request, exc: Exception):  # không lộ chi tiết nội bộ ra ngoài
        import logging
        logging.getLogger("hriam").exception("Lỗi không xử lý: %s", type(exc).__name__)
        return _error(500, "INTERNAL_ERROR", "Lỗi hệ thống. Vui lòng thử lại sau.")
