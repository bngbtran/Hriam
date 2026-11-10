#!/usr/bin/env bash
# Train mô hình dịch Ê Đê – Việt theo lời ăn tiếng nói hằng ngày, qua hai giai đoạn.
#
#   conda activate msa
#   bash scripts/train_daily.sh ede2vi        # Ê Đê -> Việt
#   bash scripts/train_daily.sh vi2ede        # Việt -> Ê Đê
#
# Giai đoạn 1 (nền): toàn bộ dữ liệu, Kinh Thánh dùng bản tiếng Việt hiện đại (Bản Phổ Thông),
#   để mô hình học từ vựng và ngữ pháp. Kết quả: runs/<hướng>-nen/
# Giai đoạn 2 (văn nói): train tiếp trên câu đời thường (ví dụ trong từ điển, câu hội thoại trong
#   data/raw/hoi_thoai/), trộn ít câu Kinh Thánh ngắn để không quên. Kết quả: runs/<hướng>-noi/
#
# Chạy lại đúng lệnh là tiếp tục từ chỗ dừng: bước nào xong rồi thì bỏ qua, đang train dở thì train tiếp.
# Bấm Ctrl+C một lần để lưu rồi dừng.
#
# Tuỳ chỉnh bằng biến môi trường, ví dụ: EPOCHS_NEN=2 bash scripts/train_daily.sh ede2vi
#   VI_VERSION   BPT (mặc định) hoặc VI1934 để dùng lại bản 1925 có sẵn, không cần cào
#   EPOCHS_NEN   số epoch giai đoạn 1 (mặc định 3)
#   EPOCHS_NOI   số epoch giai đoạn 2 (mặc định 4)
#   LR_NOI       learning rate giai đoạn 2 (mặc định 2e-5, nhỏ hơn giai đoạn 1 để không quên)
#   PYTHON       lệnh python (mặc định python)
#   TRAIN_ARGS   tham số thêm cho train.py, ví dụ TRAIN_ARGS="--limit 64" để chạy thử thật nhanh
set -euo pipefail
cd "$(dirname "$0")/.."

DIR="${1:-ede2vi}"
case "$DIR" in ede2vi|vi2ede) ;; *) echo "Hướng phải là ede2vi hoặc vi2ede"; exit 1 ;; esac
VI_VERSION="${VI_VERSION:-BPT}"
EPOCHS_NEN="${EPOCHS_NEN:-3}"
EPOCHS_NOI="${EPOCHS_NOI:-4}"
LR_NOI="${LR_NOI:-2e-5}"
PY="${PYTHON:-python}"
AWAKE=()
command -v caffeinate >/dev/null 2>&1 && AWAKE=(caffeinate -i)   # macOS: không cho máy ngủ khi train
read -r -a EXTRA <<< "${TRAIN_ARGS:-}"
# Bash 3.2 có sẵn trên macOS báo lỗi khi mở rộng mảng rỗng với set -u, nên dùng dạng ${a[@]+"${a[@]}"}.

step() { printf '\n==== %s ====\n' "$1"; }

# ---- 1. Dữ liệu nền
if [ "$VI_VERSION" = "VI1934" ]; then
  BASE=data/dataset
  step "Dữ liệu nền: Kinh Thánh tiếng Việt 1925 (data/dataset)"
  [ -s "$BASE/train.jsonl" ] || "$PY" scripts/build_dataset.py
else
  suffix="_$(echo "$VI_VERSION" | tr '[:upper:]' '[:lower:]')"
  BASE="data/dataset$suffix"
  step "Dữ liệu nền: Kinh Thánh tiếng Việt bản $VI_VERSION"
  if [ ! -s "data/interim/vi$suffix.jsonl" ]; then
    echo "Cào bản $VI_VERSION (lần đầu mất khoảng 30–60 phút; dừng giữa chừng thì chạy lại để tiếp tục)."
    "$PY" scripts/bible_scraper.py crawl --vi-version "$VI_VERSION"
  fi
  if [ ! -s "data/interim/parallel_aligned$suffix.jsonl" ]; then
    "$PY" scripts/realign.py --vi "vi$suffix.jsonl" --suffix "$suffix"
  fi
  "$PY" scripts/build_dataset.py --bible "parallel_aligned$suffix.jsonl" --out "$BASE" > /dev/null
  echo "Đã dựng $BASE"
fi

# ---- 2. Dữ liệu văn nói
step "Dữ liệu văn nói (data/dataset_noi)"
"$PY" scripts/build_daily.py --base "$BASE" --out data/dataset_noi

NEN="runs/$DIR-nen"
NOI="runs/$DIR-noi"

# ---- 3. Giai đoạn 1
step "Giai đoạn 1: train nền, $EPOCHS_NEN epoch -> $NEN"
if [ -f "$NEN/test_results.json" ]; then
  echo "Đã xong, bỏ qua. Xoá $NEN nếu muốn train lại."
else
  ${AWAKE[@]+"${AWAKE[@]}"} "$PY" scripts/train.py --direction "$DIR" --data-dir "$BASE" --run-dir "$NEN" \
    --epochs "$EPOCHS_NEN" ${EXTRA[@]+"${EXTRA[@]}"}
  if [ ! -f "$NEN/test_results.json" ]; then
    echo "Giai đoạn 1 chưa xong. Chạy lại đúng lệnh này để train tiếp."
    exit 0
  fi
fi

# ---- 4. Giai đoạn 2
step "Giai đoạn 2: train văn nói, $EPOCHS_NOI epoch, lr $LR_NOI -> $NOI"
if [ -f "$NOI/test_results.json" ]; then
  echo "Đã xong, bỏ qua. Xoá $NOI nếu muốn train lại."
else
  ${AWAKE[@]+"${AWAKE[@]}"} "$PY" scripts/train.py --direction "$DIR" --data-dir data/dataset_noi --run-dir "$NOI" \
    --init-from "$NEN/best" --epochs "$EPOCHS_NOI" --lr "$LR_NOI" ${EXTRA[@]+"${EXTRA[@]}"}
  if [ ! -f "$NOI/test_results.json" ]; then
    echo "Giai đoạn 2 chưa xong. Chạy lại đúng lệnh này để train tiếp."
    exit 0
  fi
fi

# ---- 5. Đặt làm mô hình mặc định cho scripts/translate.py
mkdir -p "runs/$DIR"
if [ -e "runs/$DIR/best" ] && [ ! -L "runs/$DIR/best" ]; then
  echo "runs/$DIR/best đã có mô hình khác; giữ nguyên. Dùng: python scripts/translate.py --direction $DIR --model $NOI/best"
else
  ln -sfn "../$DIR-noi/best" "runs/$DIR/best"
fi

step "Xong"
echo "Kết quả giai đoạn 1: $NEN/test_results.json"
echo "Kết quả giai đoạn 2: $NOI/test_results.json  (tập dev/test *_dict, *_hoithoai là câu đời thường)"
echo "Dịch thử:  python scripts/translate.py --direction $DIR \"...\""
