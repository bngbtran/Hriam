"""Alembic: dùng DATABASE_URL từ app.core.config; render_as_batch để ALTER chạy được trên SQLite."""
from alembic import context

from app import models  # noqa: F401 - nạp mọi bảng
from app.core.db import Base, engine

target_metadata = Base.metadata


def run() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


run()
