#!/usr/bin/env python3
"""Train mô hình dịch Ê Đê – Việt theo lời ăn tiếng nói hằng ngày, qua hai giai đoạn. Chạy được trên Windows và Linux.

    conda activate msa
    python scripts/train_daily.py ede2vi        # Ê Đê -> Việt
    python scripts/train_daily.py vi2ede        # Việt -> Ê Đê

Giai đoạn 1 (nền): toàn bộ dữ liệu, Kinh Thánh dùng bản tiếng Việt hiện đại (Bản Phổ Thông). -> runs/<hướng>-nen/
Giai đoạn 2 (văn nói): train tiếp trên câu đời thường, trộn ít Kinh Thánh để không quên. -> runs/<hướng>-noi/

Chỉ train trên GPU (card NVIDIA). Chạy lại đúng lệnh là tiếp tục từ chỗ dừng; Ctrl+C một lần để lưu rồi dừng.
Chạy thử vài phút:  python scripts/train_daily.py ede2vi --smoke   (dùng thư mục runs-smoke/, không ảnh hưởng bản thật)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def run(*args: str) -> None:
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    code = subprocess.call([sys.executable, *args], cwd=ROOT, env=env)
    if code:
        sys.exit(code)


def step(title: str) -> None:
    print(f"\n==== {title} ====", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("direction", choices=["ede2vi", "vi2ede"])
    parser.add_argument("--vi-version", default="BPT", choices=["BPT", "VI1934", "BD2011", "NVB"],
                        help="bản Kinh Thánh tiếng Việt; VI1934 dùng bản 1925 có sẵn, không cần cào")
    parser.add_argument("--epochs-nen", type=int, default=3)
    parser.add_argument("--epochs-noi", type=int, default=4)
    parser.add_argument("--lr-noi", default="2e-5", help="learning rate giai đoạn 2, nhỏ để không quên")
    parser.add_argument("--batch-scale", help="nhân kích thước batch; mặc định tự tính theo bộ nhớ card")
    parser.add_argument("--smoke", action="store_true", help="chạy thử nhanh với 32 cặp, kết quả ở runs-smoke/")
    args = parser.parse_args()

    runs = ROOT / ("runs-smoke" if args.smoke else "runs")
    extra = ["--batch-scale", args.batch_scale] if args.batch_scale else []
    if args.smoke:
        args.vi_version, args.epochs_nen, args.epochs_noi = "VI1934", 1, 1
        extra += ["--limit", "32"]

    # 1. Dữ liệu nền
    if args.vi_version == "VI1934":
        base = ROOT / "data" / "dataset"
        step("Dữ liệu nền: Kinh Thánh tiếng Việt 1925 (data/dataset)")
        if not (base / "train.jsonl").exists():
            run("scripts/build_dataset.py")
    else:
        suffix = f"_{args.vi_version.lower()}"
        base = ROOT / "data" / f"dataset{suffix}"
        step(f"Dữ liệu nền: Kinh Thánh tiếng Việt bản {args.vi_version}")
        if not (ROOT / "data" / "interim" / f"vi{suffix}.jsonl").exists():
            print("Cào Kinh Thánh (lần đầu mất khoảng 30–60 phút; lỗi mạng thì chạy lại để tiếp tục).", flush=True)
            run("scripts/bible_scraper.py", "crawl", "--vi-version", args.vi_version)
        if not (ROOT / "data" / "interim" / f"parallel_aligned{suffix}.jsonl").exists():
            run("scripts/realign.py", "--vi", f"vi{suffix}.jsonl", "--suffix", suffix)
        run("scripts/build_dataset.py", "--bible", f"parallel_aligned{suffix}.jsonl", "--out", str(base))

    # 2. Dữ liệu văn nói
    step("Dữ liệu văn nói (data/dataset_noi)")
    noi_data = ROOT / "data" / "dataset_noi"
    run("scripts/build_daily.py", "--base", str(base), "--out", str(noi_data))

    nen, noi = runs / f"{args.direction}-nen", runs / f"{args.direction}-noi"

    # 3. Giai đoạn nền
    step(f"Giai đoạn 1: train nền, {args.epochs_nen} epoch -> {nen.relative_to(ROOT)}")
    if (nen / "test_results.json").exists():
        print(f"Đã xong, bỏ qua. Xoá {nen.relative_to(ROOT)} nếu muốn train lại.")
    else:
        run("scripts/train.py", "--direction", args.direction, "--data-dir", str(base), "--run-dir", str(nen),
            "--epochs", str(args.epochs_nen), *extra)
        if not (nen / "test_results.json").exists():
            print("Giai đoạn 1 chưa xong. Chạy lại đúng lệnh này để train tiếp.")
            return

    # 4. Giai đoạn văn nói
    step(f"Giai đoạn 2: train văn nói, {args.epochs_noi} epoch, lr {args.lr_noi} -> {noi.relative_to(ROOT)}")
    if (noi / "test_results.json").exists():
        print(f"Đã xong, bỏ qua. Xoá {noi.relative_to(ROOT)} nếu muốn train lại.")
    else:
        run("scripts/train.py", "--direction", args.direction, "--data-dir", str(noi_data), "--run-dir", str(noi),
            "--init-from", str(nen / "best"), "--epochs", str(args.epochs_noi), "--lr", args.lr_noi, *extra)
        if not (noi / "test_results.json").exists():
            print("Giai đoạn 2 chưa xong. Chạy lại đúng lệnh này để train tiếp.")
            return

    step("Xong")
    print(f"Kết quả: {(noi / 'test_results.json').relative_to(ROOT)}  (test_dict, test_hoithoai: câu đời thường)")
    print(f"Mô hình: {(noi / 'best').relative_to(ROOT)}")
    model_arg = "" if not args.smoke else f" --model {(noi / 'best').relative_to(ROOT)}"
    print(f'Dịch thử: python scripts/translate.py --direction {args.direction}{model_arg} "..."')


if __name__ == "__main__":
    main()
