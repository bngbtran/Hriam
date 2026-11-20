"""Mỗi test chạy trên một cơ sở dữ liệu SQLite tạm, có seed vai trò và vài mục từ mẫu."""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

_tmp = Path(tempfile.mkdtemp(prefix="hriam-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["STORAGE_DIR"] = str(_tmp / "storage")
os.environ["MT_ENABLED"] = "false"
os.environ["GEMINI_API_KEY"] = ""  # test không bao giờ gọi dịch vụ ngoài, kể cả khi backend/.env có key
os.environ["SECRET_KEY"] = "test-secret-key-test-secret-key-0123456789"
os.environ["PHONE_HMAC_KEY"] = "test-phone-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.core.db import Base, SessionLocal, engine  # noqa: E402
from app.core.text import search_key  # noqa: E402
from app.main import app  # noqa: E402
from app.models import LexicalEntry, LexicalSense, Source  # noqa: E402
from app.services import accounts  # noqa: E402
from app.services.lexicon import term_index  # noqa: E402
from app.services.seed import seed_reference, seed_roles  # noqa: E402

PASSWORD = "matkhau-an-toan-1"


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    ratelimit.reset()
    with SessionLocal() as db:
        seed_roles(db)
        seed_reference(db)
        src = db.query(Source).filter_by(code="tudien-ede-viet").one()
        for form, meanings in {"Adŭ": ["Phòng", "Lớp"], "Ƀŏng": ["Ăn"], "Êsei": ["Cơm"]}.items():
            e = LexicalEntry(canonical_form=form, normalized_form=search_key(form), source_id=src.id)
            db.add(e)
            db.flush()
            for i, m in enumerate(meanings, 1):
                db.add(LexicalSense(entry_id=e.id, sense_number=i, definition_vi=m, definition_vi_key=search_key(m)))
        db.commit()
    term_index.invalidate()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def make_user(client: TestClient, username: str, roles: tuple[str, ...] = (), phone: str | None = None) -> dict:
    r = client.post("/api/v1/auth/register", json={"username": username, "display_name": username.title(),
                                                   "password": PASSWORD, "accept_terms": True, "phone": phone})
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    if roles:
        with SessionLocal() as db:
            from app.models import User
            user = db.get(User, uuid.UUID(data["user"]["id"]))
            for role in roles:
                accounts.assign_role(db, user, role)
            db.commit()
    return {"id": data["user"]["id"], "headers": {"Authorization": f"Bearer {data['access_token']}"}}


def idem() -> dict:
    return {"Idempotency-Key": str(uuid.uuid4())}
