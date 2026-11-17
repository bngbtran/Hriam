"""Adapter dịch máy (docs/02 §4): TranslationService không gắn cứng một mô hình.

Adapter hiện có: NLLB-200 distilled 600M đã tinh chỉnh (scripts/translate.py), chạy cục bộ, không gửi dữ liệu ra ngoài.
Mỗi adapter công bố: ngôn ngữ, phiên bản, giấy phép, giới hạn, có gửi dữ liệu ra ngoài hay không, chỉ số chất lượng.
"""
from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path

from ..core.config import ROOT, settings

DIRECTIONS = {("ede", "vi"): "ede2vi", ("vi", "ede"): "vi2ede"}


@dataclass
class AdapterInfo:
    direction: str
    available: bool
    model_version: str | None = None
    path: str | None = None
    license: str = "CC-BY-NC-4.0 (NLLB-200)"
    sends_data_externally: bool = False
    limits: str = f"Tối đa {settings.max_translate_chars} ký tự, 20 dòng mỗi lần"
    metrics: dict = field(default_factory=dict)


class NllbAdapter:
    def __init__(self) -> None:
        self._loaded: dict[str, object] = {}
        self._lock = threading.Lock()
        self.paths = {d: self._find(d) for d in DIRECTIONS.values()}

    @staticmethod
    def _find(direction: str) -> Path | None:
        if not settings.mt_enabled:
            return None
        given = settings.model_ede2vi if direction == "ede2vi" else settings.model_vi2ede
        candidates = [Path(given)] if given else [settings.models_dir / direction,
                                                  settings.runs_dir / f"{direction}-noi" / "best",
                                                  settings.runs_dir / direction / "best"]
        return next((p for p in candidates if (p / "config.json").exists()), None)

    def info(self, direction: str) -> AdapterInfo:
        path = self.paths.get(direction)
        if not path:
            return AdapterInfo(direction, False)
        metrics = {}
        results = next((p for p in (path / "eval" / "test_results.json", path.parent / "test_results.json")
                        if p.exists()), path / "eval" / "test_results.json")
        if results.exists():
            try:
                metrics = json.loads(results.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metrics = {}
        name = path.name if path.parent == settings.models_dir else path.parent.name
        return AdapterInfo(direction, True, f"nllb-200-distilled-600M/{name}",
                           str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path), metrics=metrics)

    def available(self, source: str, target: str) -> bool:
        return bool(self.paths.get(DIRECTIONS.get((source, target), "")))

    def translate(self, lines: list[str], source: str, target: str) -> list[str]:
        direction = DIRECTIONS[(source, target)]
        with self._lock:
            if direction not in self._loaded:
                sys.path.insert(0, str(ROOT / "scripts"))
                from translate import Translator  # noqa: PLC0415 - nạp torch chỉ khi thật sự cần
                self._loaded[direction] = Translator(str(self.paths[direction]), direction, settings.mt_beams)
            return self._loaded[direction](lines)


def download_models() -> None:
    """Tải mô hình từ repo Hugging Face riêng tư (HF_MODEL_REPO, cần HF_TOKEN) vào models_dir nếu chưa có."""
    if not settings.hf_model_repo or not settings.mt_enabled:
        return
    if all((settings.models_dir / d / "config.json").exists() for d in DIRECTIONS.values()):
        return
    from huggingface_hub import snapshot_download  # noqa: PLC0415
    snapshot_download(settings.hf_model_repo, local_dir=settings.models_dir,
                      allow_patterns=["*/config.json", "*/generation_config.json", "*/model.safetensors",
                                      "*/tokenizer*", "*/sentencepiece*", "*/special_tokens_map.json",
                                      "*/eval/test_results*.json"])


mt = NllbAdapter()


def init(preload: bool = False) -> None:
    """Gọi khi khởi động: tải mô hình (nếu cấu hình), tìm lại đường dẫn, nạp sẵn vào bộ nhớ nếu preload."""
    import logging
    log = logging.getLogger("hriam.mt")
    try:
        download_models()
    except Exception:  # thiếu token/mạng: vẫn chạy, dịch bằng ghép nghĩa
        log.exception("Không tải được mô hình từ Hugging Face")
    mt.paths = {d: mt._find(d) for d in DIRECTIONS.values()}
    log.info("Mô hình: %s", {d: str(p) if p else None for d, p in mt.paths.items()})
    if preload:
        for (src, tgt), d in DIRECTIONS.items():
            if mt.paths[d]:
                try:
                    mt.translate(["a"], src, tgt)
                except Exception:
                    log.exception("Không nạp được mô hình %s", d)
