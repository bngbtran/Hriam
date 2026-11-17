"""Dataset release: snapshot bất biến có manifest, checksum, số bản ghi và kiểm kê giấy phép (docs/03 §5, docs/04 §1)."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.db import utcnow
from ..core.deps import audit
from ..core.errors import AppError
from ..models import DatasetRelease, DatasetReleaseItem, LexicalEntry, License, Source, TranslationCorpus, User


def create_release(db: Session, actor: User, version: str, summary: str) -> DatasetRelease:
    if db.scalar(select(DatasetRelease).where(DatasetRelease.version == version)):
        raise AppError(409, "VERSION_EXISTS", "Phiên bản đã tồn tại; release là bất biến, hãy dùng số phiên bản mới.")
    entries = db.scalars(select(LexicalEntry).where(LexicalEntry.status == "published")
                         .order_by(LexicalEntry.normalized_form)).all()
    corpus = db.scalars(select(TranslationCorpus).where(
        TranslationCorpus.quality_status.in_(("community_reviewed", "expert_verified")))
        .order_by(TranslationCorpus.created_at)).all()
    records, items = [], []
    for e in entries:
        version_tag = e.updated_at.isoformat()
        records.append({"type": "lexical_entry", "id": str(e.id), "version": version_tag, "form": e.canonical_form,
                        "entry_type": e.entry_type, "source": e.source.code if e.source else None,
                        "senses": [{"n": s.sense_number, "vi": s.definition_vi, "status": s.status}
                                   for s in e.senses if s.status != "deprecated"]})
        items.append(("lexical_entry", e.id, version_tag))
    for c in corpus:
        tag = (c.verified_at or c.created_at).isoformat()
        records.append({"type": "translation_pair", "id": str(c.id), "version": tag, "source_lang": c.source_lang,
                        "source": c.source_text, "target": c.target_text, "quality": c.quality_status})
        items.append(("translation_pair", c.id, tag))
    licenses = [{"name": lic.spdx_id_or_custom_name, "review_status": lic.review_status,
                 "commercial_allowed": lic.commercial_allowed, "training_allowed": lic.training_allowed,
                 "sources": [s.code for s in db.scalars(select(Source).where(Source.license_id == lic.id))]}
                for lic in db.scalars(select(License))]
    blocked = [lic["name"] for lic in licenses if lic["review_status"] != "approved" and lic["sources"]]
    manifest = {"version": version, "created_at": utcnow().isoformat(), "summary": summary,
                "production_ready": not blocked, "licenses_pending_review": blocked,
                "counts": {"lexical_entry": len(entries), "translation_pair": len(corpus)}, "licenses": licenses,
                "records": records}
    body = json.dumps(manifest, ensure_ascii=False, indent=1).encode("utf-8")
    checksum = hashlib.sha256(body).hexdigest()
    folder = settings.storage_dir / "releases"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"dataset-{version}.json"
    path.write_bytes(body)
    release = DatasetRelease(version=version, manifest_uri=f"storage/releases/{path.name}", checksum_sha256=checksum,
                             record_counts=manifest["counts"], license_inventory=licenses, change_summary=summary,
                             created_by=actor.id, status="released" if not blocked else "research_only")
    db.add(release)
    db.flush()
    db.add_all(DatasetReleaseItem(release_id=release.id, record_type=t, record_id=i, record_version=v,
                                  inclusion_reason="published") for t, i, v in items)
    audit(db, actor, "dataset.release", "dataset_release", release.id, version=version, checksum=checksum)
    return release
