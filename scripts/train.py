#!/usr/bin/env python3
"""Train và đánh giá mô hình dịch Ê Đê – Việt trên toàn bộ data/dataset/.

    conda activate msa
    python scripts/train.py --check            # chỉ kiểm tra dữ liệu, không train
    caffeinate -i python scripts/train.py      # train đầy đủ, Ê Đê → Việt
    python scripts/train.py --direction vi2ede # hướng ngược lại, lưu ở thư mục riêng
    python scripts/train.py --rebuild-data     # dựng lại dữ liệu từ các file nguồn rồi train
    python scripts/train.py --data-dir data/dataset_noi --init-from runs/ede2vi-nen/best --run-dir runs/ede2vi-noi
                                               # train tiếp từ một mô hình đã có trên bộ dữ liệu khác
Train theo văn nói hằng ngày: xem scripts/train_daily.sh.

Chạy lại đúng lệnh sẽ tiếp tục từ checkpoint gần nhất. Bấm Ctrl+C một lần để lưu rồi dừng.
Kết quả nằm trong runs/<hướng>/: best/, last/, train.log, test_results.json, predictions_*.jsonl.

Tinh chỉnh NLLB (giấy phép CC-BY-NC, chỉ dùng phi thương mại). NLLB không có tiếng Ê Đê nên
mượn mã ace_Latn (tiếng Aceh, cùng nhóm Chăm).
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import sacrebleu  # noqa: E402
import torch  # noqa: E402
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
DATA_DIR = ROOT / "data" / "dataset"
MODEL_NAME = "facebook/nllb-200-distilled-600M"
LANG_CODES = {"ede": "ace_Latn", "vi": "vie_Latn"}
DIRECTIONS = {"ede2vi": ("ede", "vi"), "vi2ede": ("vi", "ede")}
REBUILD_STEPS = ["realign.py", "build_dataset.py"]
SEED = 42

# GPU của Mac biên dịch lại mỗi khi đổi kích thước tensor, nên chỉ dùng vài độ dài cố định.
# Bộ nhớ tăng rất nhanh theo độ dài câu, nên câu càng dài thì batch càng nhỏ (đã đo với 24 GB RAM).
BATCH_BY_LENGTH = {32: 32, 64: 16, 96: 7, 128: 4}
MAX_LENGTH = max(BATCH_BY_LENGTH)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--direction", choices=DIRECTIONS, default="ede2vi")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--lr", type=float, default=5e-5)
    parser.add_argument("--beams", type=int, default=4, help="số beam khi sinh câu để đánh giá")
    parser.add_argument("--save-every", type=int, default=1000, help="lưu checkpoint sau mỗi N bước")
    parser.add_argument("--run-dir", type=Path, help="mặc định runs/<hướng>")
    parser.add_argument("--check", action="store_true", help="chỉ kiểm tra dữ liệu rồi thoát")
    parser.add_argument("--rebuild-data", action="store_true", help="dựng lại data/dataset trước khi train")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR,
                        help="thư mục có train.jsonl, dev_*.jsonl, test_*.jsonl (mặc định data/dataset)")
    parser.add_argument("--init-from", help="bắt đầu từ mô hình này thay vì NLLB gốc, ví dụ runs/ede2vi-nen/best")
    parser.add_argument("--limit", type=int, help="chỉ dùng N cặp mỗi tập, để thử nhanh")
    parser.add_argument("--stop-after", type=int, help="dừng sau N bước tổng cộng, để thử nhanh")
    return parser.parse_args()


class Logger:
    def __init__(self, path: Path | None = None):
        self.path = path

    def __call__(self, message: str) -> None:
        print(message, flush=True)
        if self.path:
            with self.path.open("a", encoding="utf-8") as out:
                out.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")


def build_data() -> None:
    for script in REBUILD_STEPS:
        print(f"Đang chạy {script}", flush=True)
        subprocess.run([sys.executable, "-W", "ignore", str(SCRIPTS / script)], check=True, cwd=ROOT)


def load_split(name: str, src: str, tgt: str, limit: int | None) -> list[dict]:
    path = DATA_DIR / f"{name}.jsonl"
    if not path.exists():
        sys.exit(f"LỖI: không thấy {path}. Hãy chạy với --rebuild-data.")
    with path.open(encoding="utf-8") as source:
        rows = [json.loads(line) for line in source]
    bad = [i for i, row in enumerate(rows, 1) if not row.get(src, "").strip() or not row.get(tgt, "").strip()]
    if bad:
        sys.exit(f"LỖI: {path} có {len(bad)} dòng thiếu nội dung, ví dụ dòng {bad[0]}.")
    if limit and limit < len(rows):
        rows = random.Random(SEED).sample(rows, limit)
    return rows


def split_names(prefix: str) -> list[str]:
    names = sorted(p.stem for p in DATA_DIR.glob(f"{prefix}_*.jsonl"))
    if not names:
        sys.exit(f"LỖI: {DATA_DIR} không có file {prefix}_*.jsonl.")
    return names


def attach_lengths(rows: list[dict], tokenizer, src: str, tgt: str) -> None:
    sources = tokenizer([row[src] for row in rows])["input_ids"]
    targets = tokenizer(text_target=[row[tgt] for row in rows])["input_ids"]
    for row, source, target in zip(rows, sources, targets):
        row["length"] = max(len(source), len(target))


def bucket_length(length: int) -> int:
    return next((size for size in sorted(BATCH_BY_LENGTH) if length <= size), MAX_LENGTH)


def make_batches(rows: list[dict], epoch: int) -> list[tuple[int, list[dict]]]:
    """Thứ tự chỉ phụ thuộc epoch, nhờ đó chạy tiếp có thể bỏ đúng các bước đã làm."""
    rng = random.Random(SEED + epoch)
    groups: dict[int, list[dict]] = {}
    for row in rows:
        groups.setdefault(bucket_length(row["length"]), []).append(row)
    batches = []
    for size in sorted(groups):
        group = groups[size]
        rng.shuffle(group)
        step = BATCH_BY_LENGTH[size]
        batches += [(size, group[i:i + step]) for i in range(0, len(group), step)]
    rng.shuffle(batches)
    return batches


class Trainer:
    def __init__(self, args: argparse.Namespace, log: Logger):
        self.args, self.log = args, log
        self.src, self.tgt = DIRECTIONS[args.direction]
        self.device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
        self.run_dir = args.run_dir or ROOT / "runs" / args.direction
        self.last_dir, self.best_dir = self.run_dir / "last", self.run_dir / "best"
        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_NAME, src_lang=LANG_CODES[self.src], tgt_lang=LANG_CODES[self.tgt])
        self.target_id = self.tokenizer.convert_tokens_to_ids(LANG_CODES[self.tgt])
        self.state = {"epoch": 0, "step": 0, "total_steps": 0, "best": -1.0, "history": [], "before": None}

    def load_data(self) -> None:
        limit = self.args.limit
        self.train = load_split("train", self.src, self.tgt, limit)
        # Mọi file dev_*.jsonl và test_*.jsonl trong thư mục dữ liệu; mô hình tốt nhất chọn theo chrF trung bình các tập dev.
        self.dev = {name: load_split(name, self.src, self.tgt, limit) for name in split_names("dev")}
        self.test = {name: load_split(name, self.src, self.tgt, limit) for name in split_names("test")}
        self.log(f"Dữ liệu: {DATA_DIR}; dev: {', '.join(self.dev)}; test: {', '.join(self.test)}")
        attach_lengths(self.train, self.tokenizer, self.src, self.tgt)
        total = len(self.train)
        self.train = [row for row in self.train if row["length"] <= MAX_LENGTH]
        self.log(f"train: dùng {len(self.train)}/{total} cặp, bỏ {total - len(self.train)} cặp "
                 f"dài hơn {MAX_LENGTH} token.")
        for name, rows in {**self.dev, **self.test}.items():
            attach_lengths(rows, self.tokenizer, self.src, self.tgt)
            over = sum(row["length"] > MAX_LENGTH for row in rows)
            self.log(f"{name}: {len(rows)} cặp, {over} cặp có câu bị cắt khi đánh giá.")
        counts: dict[int, int] = {}
        for row in self.train:
            counts[bucket_length(row["length"])] = counts.get(bucket_length(row["length"]), 0) + 1
        self.log(f"Số cặp theo độ dài: {dict(sorted(counts.items()))}")
        self.steps_per_epoch = len(make_batches(self.train, 0))
        self.log(f"Mỗi epoch {self.steps_per_epoch} bước.")

    def setup(self) -> None:
        total = self.args.epochs * self.steps_per_epoch
        saved = self.last_dir / "train_state.pt"
        source = self.last_dir if saved.exists() else (self.args.init_from or MODEL_NAME)
        if source != self.last_dir:
            self.log(f"Bắt đầu từ mô hình {source}")
        self.model = AutoModelForSeq2SeqLM.from_pretrained(source).to(self.device)
        self.model.generation_config.max_length = None
        self.optimizer = torch.optim.AdamW(self.model.parameters(), lr=self.args.lr, weight_decay=0.01)
        warmup = max(1, int(0.05 * total))
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(
            self.optimizer,
            lambda step: min((step + 1) / warmup, max(0.0, (total - step) / max(1, total - warmup))))
        if saved.exists():
            checkpoint = torch.load(saved, map_location=self.device, weights_only=False)
            self.optimizer.load_state_dict(checkpoint["optimizer"])
            self.scheduler.load_state_dict(checkpoint["scheduler"])
            self.state = checkpoint["state"]
            self.log(f"Tiếp tục từ epoch {self.state['epoch'] + 1}, bước {self.state['step']}.")

    def save(self, path: Path, full: bool = False) -> None:
        """Ghi vào thư mục tạm rồi đổi tên, để lỗi giữa chừng không làm hỏng bản đang có."""
        temp = path.with_name(path.name + ".tmp")
        shutil.rmtree(temp, ignore_errors=True)
        temp.mkdir(parents=True)
        self.model.save_pretrained(temp)
        self.tokenizer.save_pretrained(temp)
        if full:
            torch.save({"optimizer": self.optimizer.state_dict(), "scheduler": self.scheduler.state_dict(),
                        "state": self.state}, temp / "train_state.pt")
        shutil.rmtree(path, ignore_errors=True)
        temp.rename(path)

    @torch.no_grad()
    def translate(self, rows: list[dict]) -> list[str]:
        self.model.eval()
        groups: dict[int, list[int]] = {}
        for i, row in enumerate(rows):
            groups.setdefault(bucket_length(row["length"]), []).append(i)
        output = [""] * len(rows)
        for size, indices in sorted(groups.items()):
            step = max(1, 2 * BATCH_BY_LENGTH[size] // self.args.beams)
            for start in range(0, len(indices), step):
                part = indices[start:start + step]
                batch = self.tokenizer([rows[i][self.src] for i in part], return_tensors="pt", padding="max_length",
                                       truncation=True, max_length=size).to(self.device)
                ids = self.model.generate(**batch, forced_bos_token_id=self.target_id, num_beams=self.args.beams,
                                          max_new_tokens=MAX_LENGTH, no_repeat_ngram_size=3)
                for i, text in zip(part, self.tokenizer.batch_decode(ids, skip_special_tokens=True)):
                    output[i] = text
        if self.device == "mps":
            torch.mps.empty_cache()
        return output

    def evaluate(self, sets: dict[str, list[dict]], save_predictions: bool = False) -> dict:
        scores = {}
        for name, rows in sets.items():
            start = time.time()
            hyps = self.translate(rows)
            refs = [row[self.tgt] for row in rows]
            scores[name] = {"bleu": round(sacrebleu.corpus_bleu(hyps, [refs]).score, 2),
                            "chrf": round(sacrebleu.corpus_chrf(hyps, [refs]).score, 2),
                            "n": len(rows), "seconds": round(time.time() - start)}
            if save_predictions:
                with (self.run_dir / f"predictions_{name}.jsonl").open("w", encoding="utf-8") as out:
                    for row, hyp in zip(rows, hyps):
                        out.write(json.dumps({"source": row[self.src], "reference": row[self.tgt], "output": hyp,
                                              "ref": row.get("ref")}, ensure_ascii=False) + "\n")
                for row, hyp in list(zip(rows, hyps))[:5]:
                    self.log(f"[{name}]\n  Nguồn: {row[self.src]}\n  Đích : {row[self.tgt]}\n  Dịch : {hyp}")
        return scores

    def stop_requested(self) -> bool:
        return self.args.stop_after is not None and self.state["total_steps"] >= self.args.stop_after

    def train_epoch(self, epoch: int) -> bool:
        """Trả về False nếu dừng giữa chừng."""
        batches = make_batches(self.train, epoch)
        start_step = self.state["step"]
        self.model.train()
        started, pairs, running = time.time(), 0, 0.0
        for step, (size, batch) in enumerate(batches[start_step:], start_step + 1):
            encoded = self.tokenizer([row[self.src] for row in batch], text_target=[row[self.tgt] for row in batch],
                                     return_tensors="pt", padding="max_length", truncation=True, max_length=size)
            encoded["labels"][encoded["labels"] == self.tokenizer.pad_token_id] = -100
            loss = self.model(**encoded.to(self.device)).loss
            if not torch.isfinite(loss):
                raise RuntimeError(f"Loss không hợp lệ ở epoch {epoch + 1}, bước {step}: {loss.item()}")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()
            self.scheduler.step()
            self.optimizer.zero_grad(set_to_none=True)
            running += loss.item()
            pairs += len(batch)
            self.state["step"] = step
            self.state["total_steps"] += 1
            done = step - start_step
            if done % 100 == 0 or step == len(batches):
                speed = pairs / (time.time() - started)
                left = (len(self.train) * (self.args.epochs - epoch) - pairs
                        - sum(len(b) for _, b in batches[:start_step])) / speed
                self.log(f"epoch {epoch + 1}/{self.args.epochs} bước {step}/{len(batches)} "
                         f"loss {running / done:.3f} {speed:.1f} cặp/giây, còn khoảng {left / 3600:.1f} giờ "
                         f"(chưa tính đánh giá)")
            if step < len(batches) and step % self.args.save_every == 0:
                self.save(self.last_dir, full=True)
            if self.stop_requested():
                self.save(self.last_dir, full=True)
                self.log(f"Dừng theo --stop-after ở bước {step}.")
                return False
        self.state["last_loss"] = running / max(1, len(batches) - start_step)
        return True

    def run(self) -> None:
        if self.state["before"] is None:
            self.state["before"] = self.evaluate(self.dev)
            self.log(f"Dev trước khi train: {self.state['before']}")
        for epoch in range(self.state["epoch"], self.args.epochs):
            if not self.train_epoch(epoch):
                return
            scores = self.evaluate(self.dev)
            mean_chrf = sum(score["chrf"] for score in scores.values()) / len(scores)
            self.state["epoch"], self.state["step"] = epoch + 1, 0
            self.state["history"].append({"epoch": epoch + 1, "loss": self.state.get("last_loss"), "dev": scores})
            self.log(f"Dev sau epoch {epoch + 1}: {scores}")
            if mean_chrf > self.state["best"]:
                self.state["best"] = mean_chrf
                self.save(self.best_dir)
                self.log(f"Lưu bản tốt nhất, chrF trung bình {mean_chrf:.2f}.")
            self.save(self.last_dir, full=True)
            self.model.train()
        self.finish()

    def finish(self) -> None:
        """Tập test chỉ được chấm ở đây, sau khi đã chọn xong mô hình bằng tập dev."""
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.best_dir).to(self.device)
        self.model.generation_config.max_length = None
        results = self.evaluate(self.test, save_predictions=True)
        (self.run_dir / "test_results.json").write_text(json.dumps(
            {"test": results, "before_training_dev": self.state["before"], "history": self.state["history"]},
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.log(f"TEST: {results}")
        self.log(f"Xong. Mô hình tốt nhất ở {self.best_dir}")


def main() -> None:
    args = parse_args()
    random.seed(SEED)
    torch.manual_seed(SEED)
    global DATA_DIR
    DATA_DIR = args.data_dir.resolve()
    if args.init_from and not (Path(args.init_from) / "config.json").exists():
        sys.exit(f"LỖI: không thấy mô hình ở {args.init_from}. Hãy train giai đoạn trước.")
    if args.rebuild_data or not (DATA_DIR / "train.jsonl").exists():
        build_data()
    if args.check:
        log = Logger()
        trainer = Trainer(args, log)
        log(f"Thiết bị: {trainer.device}")
        trainer.load_data()
        size, batch = make_batches(trainer.train, 0)[0]
        encoded = trainer.tokenizer([row[trainer.src] for row in batch],
                                    text_target=[row[trainer.tgt] for row in batch], return_tensors="pt",
                                    padding="max_length", truncation=True, max_length=size)
        log(f"Batch mẫu: {encoded['input_ids'].shape}, mã đầu vào {trainer.tokenizer.decode(encoded['input_ids'][0][:1])},"
            f" mã đích {trainer.tokenizer.decode(encoded['labels'][0][:1])}")
        log("Dữ liệu ổn, có thể train.")
        return

    run_dir = args.run_dir or ROOT / "runs" / args.direction
    run_dir.mkdir(parents=True, exist_ok=True)
    log = Logger(run_dir / "train.log")
    trainer = Trainer(args, log)
    log(f"Hướng {args.direction}, thiết bị {trainer.device}, {args.epochs} epoch, lr {args.lr}")
    trainer.load_data()
    trainer.setup()
    try:
        trainer.run()
    except KeyboardInterrupt:
        log("Nhận Ctrl+C, đang lưu checkpoint.")
        trainer.save(trainer.last_dir, full=True)
        log("Đã lưu. Chạy lại đúng lệnh để tiếp tục.")


if __name__ == "__main__":
    main()
