"""Dữ liệu khởi tạo: vai trò/quyền, chuẩn chữ viết nháp, nguồn và giấy phép (docs/11), nhập từ điển nguồn."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import ROOT
from ..core.permissions import PERMISSIONS, ROLES
from ..core.text import search_key
from ..models import (CorpusExample, LexicalEntry, LexicalForm, LexicalSense, License, OrthographyProfile,
                      Permission, Role, RolePermission, SenseExample, Source)
from .lexicon import term_index

DICTIONARY = ROOT / "data" / "dictionary" / "dictionary_full.json"

LICENSES = [
    {"spdx_id_or_custom_name": "Chưa xác định — Từ điển Êđê–Việt (bản scan)", "review_status": "pending",
     "notes": "Sách còn bản quyền. Cần xin phép đơn vị sở hữu trước khi dùng cho production (docs/04 §3)."},
    {"spdx_id_or_custom_name": "CC-BY-NC-4.0", "commercial_allowed": False, "redistribution_allowed": True,
     "derivatives_allowed": True, "attribution_required": True, "training_allowed": None,
     "terms_url": "https://creativecommons.org/licenses/by-nc/4.0/", "review_status": "pending",
     "notes": "Dùng cho NIRVLab/rhade-vietnamese-mt; chỉ phi thương mại. Kiểm tra commit/số dòng trước khi nhập."},
    {"spdx_id_or_custom_name": "Đóng góp cộng đồng Hriăm (theo consent từng bản ghi)", "commercial_allowed": False,
     "redistribution_allowed": True, "derivatives_allowed": True, "attribution_required": True,
     "training_allowed": None, "review_status": "approved",
     "notes": "Phạm vi dùng theo consent_scope của từng đóng góp; huấn luyện chỉ khi có consent model_training."},
]

SOURCES = [
    {"code": "tudien-ede-viet", "name": "Từ điển Êđê – Việt (bản scan, nhóm Hriăm số hoá)", "source_type": "dictionary",
     "url_or_reference": "data/raw/TuDienEDe.pdf", "license": 0,
     "notes": "Bản scan thiếu trang sách 146–147. Số hoá bằng OCR + rà soát thủ công, chưa có chuyên gia xác minh."},
    {"code": "nirvlab-rhade", "name": "Rhade–Vietnamese MT dataset (NIRVLab)", "source_type": "corpus",
     "url_or_reference": "https://huggingface.co/datasets/NIRVLab/rhade-vietnamese-mt", "license": 1,
     "notes": "SRC-001. Chưa nhập."},
    {"code": "community", "name": "Đóng góp cộng đồng Hriăm", "source_type": "community", "license": 2},
]

DIACRITIC_NAMES = {"ă": "a trăng", "â": "a mũ", "ƀ": "b có gạch (b hút hơi)", "č": "c có dấu móc (ch)",
                   "đ": "đ", "ĕ": "e trăng", "ê": "ê", "ê̆": "ê trăng", "ĭ": "i trăng", "ñ": "n ngã (nh)",
                   "ŏ": "o trăng", "ô": "ô", "ô̆": "ô trăng", "ơ": "ơ", "ơ̆": "ơ trăng", "ŭ": "u trăng", "ư": "ư",
                   "ư̆": "ư trăng"}


# Ký tự đặc thù theo bảng chữ cái của từ điển nguồn (chỉ bảng chữ, không chứa nội dung từ điển).
EDE_CHARACTERS = [
 {
  "char": "ă",
  "upper": "Ă",
  "name": "a trăng",
  "note": "ă"
 },
 {
  "char": "â",
  "upper": "Â",
  "name": "a mũ",
  "note": "â (â + o thành vần: âo- đọc là au)"
 },
 {
  "char": "ƀ",
  "upper": "Ƀ",
  "name": "b có gạch (b hút hơi)",
  "note": "b"
 },
 {
  "char": "č",
  "upper": "Č",
  "name": "c có dấu móc (ch)",
  "note": "ch"
 },
 {
  "char": "đ",
  "upper": "Đ",
  "name": "đ",
  "note": "đ"
 },
 {
  "char": "ĕ",
  "upper": "Ĕ",
  "name": "e trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ê",
  "upper": "Ê",
  "name": "ê",
  "note": "ê"
 },
 {
  "char": "ê̆",
  "upper": "Ê̆",
  "name": "ê trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ĭ",
  "upper": "Ĭ",
  "name": "i trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ñ",
  "upper": "Ñ",
  "name": "n ngã (nh)",
  "note": "nh"
 },
 {
  "char": "ŏ",
  "upper": "Ŏ",
  "name": "o trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ô",
  "upper": "Ô",
  "name": "ô",
  "note": "ô"
 },
 {
  "char": "ô̆",
  "upper": "Ô̆",
  "name": "ô trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ơ",
  "upper": "Ơ",
  "name": "ơ",
  "note": "ơ"
 },
 {
  "char": "ơ̆",
  "upper": "Ơ̆",
  "name": "ơ trăng",
  "note": "â"
 },
 {
  "char": "ŭ",
  "upper": "Ŭ",
  "name": "u trăng",
  "note": "không có âm tương ứng"
 },
 {
  "char": "ư",
  "upper": "Ư",
  "name": "ư",
  "note": "ư"
 },
 {
  "char": "ư̆",
  "upper": "Ư̆",
  "name": "ư trăng",
  "note": "không có âm tương ứng"
 }
]


def seed_roles(db: Session) -> None:
    perms = {}
    for code, desc in PERMISSIONS.items():
        perm = db.scalar(select(Permission).where(Permission.code == code)) or Permission(code=code)
        perm.description = desc
        db.add(perm)
        perms[code] = perm
    db.flush()
    for name, (desc, codes) in ROLES.items():
        role = db.scalar(select(Role).where(Role.name == name)) or Role(name=name)
        role.description = desc
        db.add(role)
        db.flush()
        have = {rp.permission.code for rp in role.permissions}
        for code in codes:
            if code not in have:
                role.permissions.append(RolePermission(permission=perms[code]))
        for rp in list(role.permissions):
            if rp.permission.code not in codes:
                role.permissions.remove(rp)
    db.flush()


def seed_reference(db: Session) -> None:
    licenses = []
    for data in LICENSES:
        lic = db.scalar(select(License).where(License.spdx_id_or_custom_name == data["spdx_id_or_custom_name"]))
        if not lic:
            lic = License(**data)
            db.add(lic)
            db.flush()
        licenses.append(lic)
    for data in SOURCES:
        if not db.scalar(select(Source).where(Source.code == data["code"])):
            data = dict(data)
            db.add(Source(license_id=licenses[data.pop("license")].id, **data))
    if not db.scalar(select(OrthographyProfile).where(OrthographyProfile.code == "ede-tudien-baseline")):
        chars = list(EDE_CHARACTERS)
        db.add(OrthographyProfile(
            code="ede-tudien-baseline", name="Bảng chữ cái theo Từ điển Êđê–Việt", version="0.1",
            description="Profile nháp lấy từ bảng chữ cái của từ điển nguồn. Chờ Language Expert/hội đồng xác nhận "
                        "trước khi gọi là chuẩn (docs/04 §4.2).",
            region_scope="Chưa xác định", characters=chars, status="draft",
            examples=[{"text": "Kâo čiăng ƀơ̆ng êsei", "vi": "Tôi muốn ăn cơm"}]))
    db.flush()


def _code(value):
    return value.get("code") if isinstance(value, dict) else value


def import_dictionary(db: Session, path: Path = DICTIONARY) -> dict:
    """Nhập từ điển nguồn vào Master Lexicon với nghĩa ở trạng thái 'draft' (chưa chuyên gia xác minh).

    Idempotent: bỏ qua mục đã có source_ref. Báo cáo: imported, skipped, duplicate, examples.
    """
    source = db.scalar(select(Source).where(Source.code == "tudien-ede-viet"))
    profile = db.scalar(select(OrthographyProfile).where(OrthographyProfile.code == "ede-tudien-baseline"))
    data = json.loads(path.read_text(encoding="utf-8"))
    existing = set(db.scalars(select(LexicalEntry.source_ref).where(LexicalEntry.source_id == source.id)))
    report = {"imported": 0, "skipped": 0, "duplicate_form": 0, "examples": 0, "license_status":
              source.license.review_status if source.license else "unknown"}
    seen_forms: set[str] = set()
    # Gán id sẵn và ghi theo lô: tránh hàng nghìn lượt đi-về khi database ở xa (Supabase).
    entries, forms, senses, examples, links = [], [], [], [], []
    for item in data["entries"]:
        ref = f"{item['id']} · tr.{item['book_page']}"
        if ref in existing:
            report["skipped"] += 1
            continue
        key = search_key(item["headword"])
        if key in seen_forms:
            report["duplicate_form"] += 1  # đồng âm/đồng tự: giữ mục riêng, chuyên gia phân biệt sau
        seen_forms.add(key)
        pos = ", ".join(p["code"] for p in item.get("pos") or [])
        entry = LexicalEntry(id=uuid.uuid4(), canonical_form=item["headword"], normalized_form=key,
                             entry_type="multiword_expression" if " " in item["headword"].strip() else "word",
                             orthography_profile_id=profile.id if profile else None, source_id=source.id,
                             source_ref=ref, part_of_speech=pos or None, loan_source=_code(item.get("loan_source")),
                             notes="; ".join(item.get("notes") or []))
        entries.append(entry)
        for form in (item.get("variants") or []) + (item.get("alt_forms") or []):
            text = form if isinstance(form, str) else form.get("form") or form.get("text") or ""
            if text:
                forms.append(LexicalForm(entry_id=entry.id, form_text=text, normalized_form=search_key(text),
                                         form_type="variant", source_id=source.id))
        for n, sense in enumerate(item["senses"], 1):
            gloss = (sense.get("gloss_vi") or "").strip()
            if not gloss:
                continue
            sense_pos = sense.get("pos")
            sense_row = LexicalSense(id=uuid.uuid4(), entry_id=entry.id, sense_number=n, definition_vi=gloss,
                                     definition_vi_key=search_key(gloss), part_of_speech=_code(sense_pos),
                                     status="draft", verification_level="source_unreviewed", source_id=source.id)
            senses.append(sense_row)
            for i, ex in enumerate(sense.get("examples") or []):
                example = CorpusExample(id=uuid.uuid4(), text_ede=ex["ede"], text_vi=ex["vi"], source_id=source.id,
                                        verification_status="unreviewed")
                examples.append(example)
                links.append(SenseExample(sense_id=sense_row.id, example_id=example.id, position=i))
                report["examples"] += 1
        report["imported"] += 1
    for batch in (entries, forms, senses, examples, links):
        db.add_all(batch)
        db.flush()
    term_index.invalidate()
    return report
