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
        candidates = [Path(given)] if given else [settings.runs_dir / f"{direction}-noi" / "best",
                                                  settings.runs_dir / direction / "best"]
        return next((p for p in candidates if (p / "config.json").exists()), None)

    def info(self, direction: str) -> AdapterInfo:
        path = self.paths.get(direction)
        if not path:
            return AdapterInfo(direction, False)
        metrics = {}
        results = path.parent / "test_results.json"
        if results.exists():
            try:
                metrics = json.loads(results.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metrics = {}
        return AdapterInfo(direction, True, f"nllb-200-distilled-600M/{path.parent.name}",
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


mt = NllbAdapter()
