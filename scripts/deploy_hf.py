#!/usr/bin/env python3
"""Đưa Hriăm lên Hugging Face. Đăng nhập trước một lần: `hf auth login` (token có quyền write).

    conda activate msa
    python scripts/deploy_hf.py models --repo ten-ban/hriam-models   # tải models/ lên repo mô hình RIÊNG TƯ
    python scripts/deploy_hf.py space  --repo ten-ban/hriam-api      # tải backend lên Space (Docker, CPU Basic)

Space chỉ chứa mã backend và scripts/translate.py. Không có dữ liệu từ điển, Kinh Thánh hay mô hình:
mô hình được Space tải từ repo riêng tư khi khởi động (cần secret HF_TOKEN), từ điển nhập thẳng vào database
từ máy của bạn (xem docs/DEPLOY.md).
"""
from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODEL_FILES = ["*/config.json", "*/generation_config.json", "*/model.safetensors", "*/tokenizer*",
               "*/sentencepiece*", "*/special_tokens_map.json", "*/eval/test_results*.json"]
BACKEND_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "hriam.db*", "storage", ".env", ".pytest_cache")


def api():
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("Thiếu huggingface_hub: pip install -r backend/requirements-ml.txt")
    return HfApi()


def upload_models(repo: str) -> None:
    models = ROOT / "models"
    missing = [d for d in ("ede2vi", "vi2ede") if not (models / d / "config.json").exists()]
    if missing:
        sys.exit(f"Thiếu mô hình trong models/: {', '.join(missing)}")
    hf = api()
    hf.create_repo(repo, repo_type="model", private=True, exist_ok=True)
    print(f"Đang tải models/ lên {repo} (riêng tư), khoảng 4,6 GB...")
    hf.upload_folder(repo_id=repo, repo_type="model", folder_path=models, allow_patterns=MODEL_FILES,
                     commit_message="Cập nhật mô hình Hriăm")
    print(f"Xong: https://huggingface.co/{repo}")


def upload_space(repo: str) -> None:
    hf = api()
    hf.create_repo(repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        stage = Path(tmp)
        shutil.copy(ROOT / "deploy" / "huggingface" / "Dockerfile", stage / "Dockerfile")
        shutil.copy(ROOT / "deploy" / "huggingface" / "README.md", stage / "README.md")
        shutil.copytree(ROOT / "backend", stage / "backend", ignore=BACKEND_IGNORE)
        (stage / "scripts").mkdir()
        shutil.copy(ROOT / "scripts" / "translate.py", stage / "scripts" / "translate.py")
        print(f"Đang tải backend lên Space {repo}...")
        hf.upload_folder(repo_id=repo, repo_type="space", folder_path=stage, delete_patterns="*",
                         commit_message="Cập nhật backend Hriăm")
    user, name = repo.split("/", 1)
    print(f"Xong: https://huggingface.co/spaces/{repo}")
    print(f"API: https://{user.lower()}-{name.lower().replace('_', '-')}.hf.space/api/v1/health")
    print("Nhớ đặt biến và secret của Space theo docs/DEPLOY.md.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", choices=["models", "space"])
    parser.add_argument("--repo", required=True, help="ten-ban/ten-repo")
    args = parser.parse_args()
    (upload_models if args.target == "models" else upload_space)(args.repo)


if __name__ == "__main__":
    main()
