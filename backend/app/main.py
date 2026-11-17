"""Ứng dụng FastAPI Hriăm: modular monolith (ADR-003). Chạy: uvicorn app.main:app --reload (trong backend/)."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import admin, auth, contributions, forum, translation
from .core import errors
from .core.config import settings
from .core.errors import ok
from .integrations.mt import mt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Hriăm API", version="1.0.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs",
              description="Nền tảng ngôn ngữ và văn hoá Ê Đê ↔ tiếng Kinh. Phản hồi bọc trong {data, meta}; "
                          "lỗi trong {error}. Quyền ghi chú trong từng endpoint admin.")
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

for module in (auth, translation, forum, contributions, admin):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health():
    return ok({"status": "ok", "translation": {d: mt.info(d).available for d in ("ede2vi", "vi2ede")}})
