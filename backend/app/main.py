"""Ứng dụng FastAPI Hriăm: modular monolith (ADR-003). Chạy: uvicorn app.main:app --reload (trong backend/)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import admin, auth, contributions, conversation, culture, forum, translation
from .core import errors
from .core.config import ROOT, settings
from .core.db import engine
from .core.errors import AppError, ok
from .integrations import mt as mt_module
from .integrations.gemini import gemini
from .integrations.mt import mt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")



@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio
    # Tải/nạp mô hình ở luồng phụ để không chặn khởi động; trong lúc đó API vẫn trả bản ghép nghĩa.
    asyncio.get_running_loop().run_in_executor(None, mt_module.init, settings.mt_preload)
    yield


app = FastAPI(lifespan=lifespan, title="Hriăm API", version="1.0.0", openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs",
              description="Nền tảng ngôn ngữ và văn hoá Ê Đê ↔ tiếng Kinh. Phản hồi bọc trong {data, meta}; "
                          "lỗi trong {error}. Quyền ghi chú trong từng endpoint admin.")
errors.install(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
                   allow_headers=["Authorization", "Content-Type", "Idempotency-Key"])

for module in (auth, translation, forum, contributions, admin, conversation, culture):
    app.include_router(module.router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["system"])
def health():
    """Dùng cho UptimeRobot: có truy vấn database thật (giữ Supabase không bị tạm dừng)."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise AppError(503, "DB_UNAVAILABLE", "Không kết nối được cơ sở dữ liệu.") from exc
    return ok({"status": "ok", "database": "ok",
               "translation": {**{d: mt.info(d).available for d in ("ede2vi", "vi2ede")},
                               "gemini": gemini.available(), "provider": settings.mt_provider}})


# Phục vụ luôn bản build giao diện (npm run build trong frontend/) để chạy một cổng duy nhất, ví dụ sau tunnel.
# Không có frontend/dist thì bỏ qua; khi dev, giao diện chạy riêng bằng npm run dev.
DIST = (ROOT / "frontend" / "dist").resolve()
if (DIST / "index.html").is_file():
    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise AppError(404, "NOT_FOUND", "Không tìm thấy đường dẫn API.")
        file = (DIST / path).resolve()
        if path and file.is_file() and DIST in file.parents:
            return FileResponse(file)
        return FileResponse(DIST / "index.html")  # route phía client (React Router)
