"""Adapter dịch máy qua Gemini (tuỳ chọn). Khác NLLB cục bộ: văn bản người dùng được GỬI RA NGOÀI (Google).

Chỉ chạy khi có GEMINI_API_KEY. Cách dùng được chọn bằng MT_PROVIDER (xem core/config.py):
  local  - chỉ model cục bộ (mặc định)
  auto   - model cục bộ trước; không có hoặc lỗi thì dùng Gemini
  gemini - luôn dùng Gemini
Gemini không được train riêng cho tiếng Ê Đê, nên prompt kèm nghĩa từ và câu ví dụ lấy từ từ điển để làm ngữ cảnh.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict

from ..core.config import settings

log = logging.getLogger("hriam.gemini")

LANG_NAMES = {"ede": "tiếng Ê Đê (chữ Latinh, vùng Đắk Lắk; dùng đúng dấu ŏ ĕ ŭ ơ̆ ư̆ ê̆ ƀ č ñ ...)", "vi": "tiếng Việt"}


class GeminiAdapter:
    def __init__(self) -> None:
        self._client = None
        self._lock = threading.Lock()
        self._cache: OrderedDict[tuple, list[str]] = OrderedDict()  # câu giống hệt thì không gọi lại (nhanh và đỡ tốn credit)
        self._cache_size = 256

    def available(self) -> bool:
        return bool(settings.gemini_api_key)

    def _get_client(self):
        with self._lock:
            if self._client is None:
                from google import genai  # noqa: PLC0415 - chỉ nạp khi thật sự dùng
                from google.genai import types  # noqa: PLC0415
                self._client = genai.Client(api_key=settings.gemini_api_key,
                                            http_options=types.HttpOptions(timeout=settings.gemini_timeout_ms))
            return self._client

    @staticmethod
    def build_prompt(lines: list[str], source: str, target: str, glossary: list[str], examples: list[dict]) -> str:
        parts = [f"Dịch từ {LANG_NAMES[source]} sang {LANG_NAMES[target]}.",
                 "Luôn đưa ra bản dịch tốt nhất có thể, kể cả khi thiếu từ; mỗi dòng nguồn đúng một dòng dịch. "
                 "Chỉ in bản dịch: không giải thích, không ghi chú, không markdown, không dấu ngoặc kép.",
                 "Ưu tiên bảng từ và câu ví dụ bên dưới (lấy từ từ điển Ê Đê – Việt); chỉ dùng từ ngoài bảng khi "
                 "thật sự cần và chắc chắn là từ Ê Đê có thật."]
        if glossary:
            parts.append("Bảng từ (Ê Đê = tiếng Việt):\n" + "\n".join(glossary))
        if examples:
            parts.append("Câu ví dụ:\n" + "\n".join(f"{e['ede']} = {e['vi']}" for e in examples))
        parts.append("Văn bản cần dịch:\n" + "\n".join(lines))
        return "\n\n".join(parts)

    def translate(self, lines: list[str], source: str, target: str, glossary: list[str] | None = None,
                  examples: list[dict] | None = None) -> list[str]:
        prompt = self.build_prompt(lines, source, target, glossary or [], examples or [])
        level = settings.gemini_thinking_level
        key = (settings.gemini_model, level, prompt)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return list(self._cache[key])
        extra = {"generation_config": {"thinking_level": level}} if level else {}
        last: Exception | None = None
        for attempt in range(2):  # lỗi mạng/timeout thoáng qua: thử lại một lần
            try:
                interaction = self._get_client().interactions.create(model=settings.gemini_model, input=prompt, **extra)
            except Exception as exc:  # noqa: BLE001 - SDK ném nhiều loại lỗi
                last = exc
                log.warning("Gemini lỗi lần %d: %s", attempt + 1, exc)
                if getattr(exc, "status_code", None) in (400, 401, 402, 403, 404):
                    break  # lỗi key, thanh toán, tham số: thử lại cũng vô ích
                continue
            out = [ln.strip() for ln in (interaction.output_text or "").splitlines() if ln.strip()]
            # Trả lời dài gấp nhiều lần đầu vào là lời giải thích chứ không phải bản dịch.
            if not out or len(" ".join(out)) > 4 * len(" ".join(lines)) + 60 or "**" in " ".join(out):
                last = RuntimeError("Gemini không trả bản dịch hợp lệ.")
                continue
            with self._lock:
                self._cache[key] = out
                while len(self._cache) > self._cache_size:
                    self._cache.popitem(last=False)
            return list(out)
        raise last or RuntimeError("Gemini không trả nội dung.")

gemini = GeminiAdapter()
