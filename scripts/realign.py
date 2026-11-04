#!/usr/bin/env python3
"""Căn lại Kinh Thánh theo nội dung, vì hai bản đánh số câu khác nhau ở một số chương.

Học từ vựng dịch bằng IBM Model 1 trên từ nội dung, rồi căn đơn điệu từng sách bằng quy hoạch động.
Mặc định giữ nguyên ghép theo số câu; gộp hoặc bỏ câu bị phạt, nên chỉ xảy ra khi có bằng chứng rõ.
Vào: data/interim/vi.jsonl, ede.jsonl. Ra: data/interim/parallel_aligned.jsonl, unmatched.jsonl.
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data" / "interim"
BAND = 15          # độ lệch vị trí tối đa so với đường chéo trong một sách
EM_ITERS = 4
TOP_K = 3
MIN_PROB = 0.10
STOPWORDS = 150    # số từ phổ biến nhất mỗi ngôn ngữ bị loại khỏi phần chấm điểm
SAME_REF_BONUS = 3.0
SKIP_PENALTY = 4.0   # phạt mỗi câu bị bỏ
MERGE_PENALTY = 3.0  # phạt mỗi câu gộp thêm
MIN_COVERAGE = 0.12  # dưới mức này cặp bị coi là không khớp nghĩa (cặp ngẫu nhiên chỉ khoảng 0,02)
MOVES = [(1, 1), (1, 2), (2, 1), (1, 3), (3, 1), (1, 0), (0, 1)]
TOKEN_RE = re.compile(r"[^\W\d_][^\W\d_\u0300-\u036f]*(?:[\u0300-\u036f]+[^\W\d_]*)*(?:[-'’][^\W\d_][^\W\d_\u0300-\u036f]*(?:[\u0300-\u036f]+[^\W\d_]*)*)*")


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def load(name: str) -> dict[str, list[dict]]:
    books: dict[str, list[dict]] = defaultdict(list)
    with (DATA / name).open(encoding="utf-8") as src:
        for line in src:
            row = json.loads(line)
            row["tokens"] = tokens(row["text"])
            if row["tokens"]:  # bỏ câu giữ chỗ như "-"
                row["ref"] = f'{row["book"]}.{row["chapter"]}.' + (
                    str(row["start"]) if row["start"] == row["end"] else f'{row["start"]}-{row["end"]}')
                books[row["book"]].append(row)
    return books


def drop_stopwords(books: dict[str, list[dict]]) -> None:
    counts = Counter(t for rows in books.values() for row in rows for t in row["tokens"])
    stop = {t for t, _ in counts.most_common(STOPWORDS)}
    for rows in books.values():
        for row in rows:
            row["tokens"] = [t for t in row["tokens"] if t not in stop]


def ibm1(pairs: list[tuple[list[str], list[str]]]) -> dict[str, set[str]]:
    """Trả về {từ nguồn: tập từ đích có xác suất dịch cao nhất}."""
    prob: dict[str, dict[str, float]] = defaultdict(dict)
    for source, target in pairs:
        for s in set(source):
            for t in set(target):
                prob[s][t] = 1.0
    for _ in range(EM_ITERS):
        counts: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for source, target in pairs:
            if not source:
                continue
            for t in target:
                norm = sum(prob[s][t] for s in source)
                for s in source:
                    counts[s][t] += prob[s][t] / norm
        for s, row in counts.items():
            total = sum(row.values())
            prob[s] = {t: c / total for t, c in row.items()}
    return {
        s: {t for t, p in sorted(row.items(), key=lambda kv: -kv[1])[:TOP_K] if p >= MIN_PROB}
        for s, row in prob.items()
    }


class Scorer:
    def __init__(self, vi2ede: dict[str, set[str]], ede2vi: dict[str, set[str]]):
        self.vi2ede, self.ede2vi = vi2ede, ede2vi

    def hits(self, vi: list[list[str]], ede: list[list[str]]) -> tuple[int, int]:
        vi_tokens = [t for verse in vi for t in verse]
        ede_tokens = [t for verse in ede for t in verse]
        vi_set, ede_set = set(vi_tokens), set(ede_tokens)
        empty: set[str] = set()
        hits = sum(not self.vi2ede.get(t, empty).isdisjoint(ede_set) for t in vi_tokens)
        hits += sum(not self.ede2vi.get(t, empty).isdisjoint(vi_set) for t in ede_tokens)
        return hits, len(vi_tokens) + len(ede_tokens)

    def coverage(self, vi, ede) -> float:
        hit, total = self.hits(vi, ede)
        return hit / max(1, total)


def align_book(vi: list[dict], ede: list[dict], scorer: Scorer, baseline: float) -> list[tuple[list[dict], list[dict]]]:
    n, m = len(vi), len(ede)
    best: dict[tuple[int, int], tuple[float, tuple[int, int] | None]] = {(0, 0): (0.0, None)}
    for i in range(n + 1):
        low = max(0, round(i * m / max(1, n)) - BAND)
        high = min(m, round(i * m / max(1, n)) + BAND)
        for j in range(low, high + 1):
            if (i, j) == (0, 0):
                continue
            top, back = float("-inf"), None
            for a, b in MOVES:
                prev = best.get((i - a, j - b))
                if prev is None or i < a or j < b:
                    continue
                gain = -SKIP_PENALTY if not (a and b) else -MERGE_PENALTY * (a + b - 2)
                if a and b:
                    hit, total = scorer.hits([v["tokens"] for v in vi[i - a:i]], [e["tokens"] for e in ede[j - b:j]])
                    gain += hit - baseline * total
                    if a == b == 1 and vi[i - 1]["ref"] == ede[j - 1]["ref"]:
                        gain += SAME_REF_BONUS
                if prev[0] + gain > top:
                    top, back = prev[0] + gain, (a, b)
            if back is not None:
                best[(i, j)] = (top, back)
    if (n, m) not in best:
        raise RuntimeError("Không tìm được đường căn; hãy tăng BAND")
    path = []
    i, j = n, m
    while (i, j) != (0, 0):
        a, b = best[(i, j)][1]
        path.append((vi[i - a:i], ede[j - b:j]))
        i, j = i - a, j - b
    return path[::-1]


def calibrate(scorer: Scorer, pairs: list[tuple[list[str], list[str]]]) -> tuple[float, float, float]:
    """Độ phủ từ vựng của cặp theo ref và của cặp ngẫu nhiên; ngưỡng đặt ở giữa."""
    rng = random.Random(0)
    sample = rng.sample(pairs, min(3000, len(pairs)))
    true_mean = sum(scorer.coverage([v], [e]) for v, e in sample) / len(sample)
    shuffled = [e for _, e in sample]
    rng.shuffle(shuffled)
    rand_mean = sum(scorer.coverage([v], [e]) for (v, _), e in zip(sample, shuffled)) / len(sample)
    return true_mean, rand_mean, (true_mean + rand_mean) / 2


def main() -> None:
    vi, ede = load("vi.jsonl"), load("ede.jsonl")
    drop_stopwords(vi)
    drop_stopwords(ede)
    ede_by_ref = {row["ref"]: row for rows in ede.values() for row in rows}
    pairs = [(row["tokens"], ede_by_ref[row["ref"]]["tokens"])
             for rows in vi.values() for row in rows if row["ref"] in ede_by_ref]
    print(f"Học từ vựng từ {len(pairs)} cặp theo số câu", flush=True)
    scorer = Scorer(ibm1(pairs), ibm1([(e, v) for v, e in pairs]))
    true_mean, rand_mean, baseline = calibrate(scorer, pairs)
    print(f"Độ phủ: theo số câu {true_mean:.3f}, ngẫu nhiên {rand_mean:.3f}, ngưỡng {baseline:.3f}", flush=True)
    aligned = []
    for book in vi:
        for vi_part, ede_part in align_book(vi[book], ede[book], scorer, baseline):
            aligned.append((book, vi_part, ede_part))

    moved = merged = 0
    with (DATA / "parallel_aligned.jsonl").open("w", encoding="utf-8") as out, \
            (DATA / "unmatched.jsonl").open("w", encoding="utf-8") as lost:
        for _book, vi_part, ede_part in aligned:
            ref_vi = "+".join(v["ref"] for v in vi_part)
            ref_ede = "+".join(e["ref"] for e in ede_part)
            vi_text = " ".join(v["text"] for v in vi_part)
            ede_text = " ".join(e["text"] for e in ede_part)
            if not (vi_part and ede_part):
                lost.write(json.dumps({"ref_vi": ref_vi, "ref_ede": ref_ede, "vi": vi_text, "ede": ede_text},
                                      ensure_ascii=False) + "\n")
                continue
            moved += ref_vi != ref_ede
            merged += len(vi_part) + len(ede_part) > 2
            coverage = scorer.coverage([v["tokens"] for v in vi_part], [e["tokens"] for e in ede_part])
            out.write(json.dumps({"ref_vi": ref_vi, "ref_ede": ref_ede, "vi": vi_text, "ede": ede_text,
                                  "coverage": round(coverage, 3), "low_coverage": coverage < MIN_COVERAGE},
                                 ensure_ascii=False) + "\n")
    kept = sum(1 for _, a, b in aligned if a and b)
    print(f"{kept} cặp, {moved} cặp có ref hai bản khác nhau, {merged} khối gộp, {len(aligned) - kept} câu không có cặp")


if __name__ == "__main__":
    main()
