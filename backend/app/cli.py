"""Lệnh quản trị (chạy trong backend/):

    python -m app.cli migrate                     # tạo/cập nhật bảng bằng Alembic
    python -m app.cli seed                        # vai trò, quyền, nguồn, giấy phép, chuẩn chữ viết nháp
    python -m app.cli import-dictionary           # nhập từ điển nguồn vào Master Lexicon (nghĩa ở trạng thái draft)
    python -m app.cli create-admin --username admin --display-name "Quản trị"   # hỏi mật khẩu
    python -m app.cli grant --username lan --role language_expert
    python -m app.cli setup                       # migrate + seed + import-dictionary
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys

from sqlalchemy import select

from .core.config import BACKEND
from .core.db import SessionLocal


def migrate() -> None:
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "migrations"))
    command.upgrade(cfg, "head")
    print("Đã cập nhật cấu trúc cơ sở dữ liệu.")


def seed() -> None:
    from .services.seed import seed_reference, seed_roles
    with SessionLocal() as db:
        seed_roles(db)
        seed_reference(db)
        db.commit()
    print("Đã tạo vai trò, quyền, nguồn, giấy phép và chuẩn chữ viết nháp.")


def import_dictionary() -> None:
    from .services.seed import import_dictionary as run
    with SessionLocal() as db:
        report = run(db)
        db.commit()
    print("Nhập từ điển:", json.dumps(report, ensure_ascii=False))


def create_admin(username: str, display_name: str) -> None:
    from .models import User
    from .services import accounts
    password = getpass.getpass("Mật khẩu (≥ 10 ký tự): ")
    if password != getpass.getpass("Nhập lại: "):
        sys.exit("Mật khẩu không khớp.")
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            user = accounts.register(db, username, display_name, password, None, None)
        accounts.assign_role(db, user, "admin")
        db.commit()
    print(f"Tài khoản {username} có quyền admin.")


def grant(username: str, role: str) -> None:
    from .models import User
    from .services import accounts
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == username))
        if not user:
            sys.exit(f"Không có người dùng {username}.")
        accounts.assign_role(db, user, role)
        db.commit()
    print(f"Đã gán vai trò {role} cho {username}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("migrate", "seed", "import-dictionary", "setup"):
        sub.add_parser(name)
    p = sub.add_parser("create-admin")
    p.add_argument("--username", required=True)
    p.add_argument("--display-name", default="Quản trị viên")
    p = sub.add_parser("grant")
    p.add_argument("--username", required=True)
    p.add_argument("--role", required=True,
                   choices=["user", "trusted_contributor", "language_expert", "moderator", "admin"])
    args = parser.parse_args()
    if args.cmd in ("migrate", "setup"):
        migrate()
    if args.cmd in ("seed", "setup"):
        seed()
    if args.cmd in ("import-dictionary", "setup"):
        import_dictionary()
    if args.cmd == "create-admin":
        create_admin(args.username, args.display_name)
    if args.cmd == "grant":
        grant(args.username, args.role)


if __name__ == "__main__":
    main()
