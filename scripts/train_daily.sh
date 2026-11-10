#!/usr/bin/env bash
# Giữ cho lệnh cũ vẫn chạy được; nội dung chính nằm ở scripts/train_daily.py.
#   bash scripts/train_daily.sh ede2vi [--smoke] [--vi-version VI1934] ...
cd "$(dirname "$0")/.." && exec "${PYTHON:-python}" scripts/train_daily.py "$@"
