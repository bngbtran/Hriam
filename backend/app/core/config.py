"""Cấu hình đọc từ biến môi trường (file backend/.env nếu có). Không ghi secret vào code."""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
ROOT = BACKEND.parent


def _load_env_file() -> None:
    env = BACKEND / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


_load_env_file()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    env: str = _env("HRIAM_ENV", "development")
    # SQLite cho phát triển; production đặt postgresql+psycopg://user:pass@host/db
    database_url: str = _env("DATABASE_URL", f"sqlite:///{BACKEND / 'hriam.db'}")
    secret_key: str = _env("SECRET_KEY", "")
    phone_hmac_key: str = _env("PHONE_HMAC_KEY", "")
    phone_hmac_key_version: str = _env("PHONE_HMAC_KEY_VERSION", "v1")
    access_token_minutes: int = int(_env("ACCESS_TOKEN_MINUTES", "15"))
    refresh_token_days: int = int(_env("REFRESH_TOKEN_DAYS", "14"))
    cors_origins: list[str] = field(default_factory=lambda: [o for o in _env(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o])
    cookie_secure: bool = _env("COOKIE_SECURE", "false").lower() == "true"
    storage_dir: Path = Path(_env("STORAGE_DIR", str(BACKEND / "storage")))
    models_dir: Path = Path(_env("MODELS_DIR", str(ROOT / "models")))
    runs_dir: Path = Path(_env("RUNS_DIR", str(ROOT / "runs")))
    # Repo mô hình riêng tư trên Hugging Face (vd. ten-ban/hriam-models); tải về models_dir khi khởi động nếu thiếu
    hf_model_repo: str = _env("HF_MODEL_REPO", "")
    mt_preload: bool = _env("MT_PRELOAD", "false").lower() == "true"
    # Chạy sau proxy (Vercel rewrite, Hugging Face): lấy IP người dùng từ X-Forwarded-For
    trust_proxy: bool = _env("TRUST_PROXY", "false").lower() == "true"
    model_ede2vi: str = _env("MODEL_EDE2VI", "")
    model_vi2ede: str = _env("MODEL_VI2EDE", "")
    mt_enabled: bool = _env("MT_ENABLED", "true").lower() == "true"
    mt_beams: int = int(_env("MT_BEAMS", "4"))
    max_translate_chars: int = int(_env("MAX_TRANSLATE_CHARS", "1000"))
    # Gemini (tuỳ chọn, gửi văn bản ra ngoài). MT_PROVIDER: local | auto (local trước, lỗi/thiếu thì Gemini) | gemini
    mt_provider: str = _env("MT_PROVIDER", "auto").lower()
    gemini_api_key: str = _env("GEMINI_API_KEY", "")
    gemini_model: str = _env("GEMINI_MODEL", "gemini-4-hydrogen")
    gemini_timeout_ms: int = int(_env("GEMINI_TIMEOUT_MS", "30000"))
    # Mức "suy nghĩ" của Gemini: minimal | low | medium | high. Để trống = mặc định của model. Thấp hơn thì nhanh hơn.
    gemini_thinking_level: str = _env("GEMINI_THINKING_LEVEL", "")
    moderation_policy_version: str = _env("MODERATION_POLICY_VERSION", "2026.11-rules-v1")


settings = Settings()

if not settings.secret_key or not settings.phone_hmac_key:
    if settings.env == "production":
        raise RuntimeError("Thiếu SECRET_KEY hoặc PHONE_HMAC_KEY trong môi trường production.")
    # Dev: khoá ngẫu nhiên mỗi lần chạy (đăng nhập mất khi khởi động lại). Đặt trong backend/.env để giữ.
    object.__setattr__(settings, "secret_key", settings.secret_key or secrets.token_urlsafe(48))
    object.__setattr__(settings, "phone_hmac_key", settings.phone_hmac_key or secrets.token_urlsafe(48))
