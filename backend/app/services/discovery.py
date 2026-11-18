"""Dịch vụ Automatic Lexical Discovery (docs/01 §4.7, docs/04 §6, docs/03 §7).

Quy trình:
1. Lọc nội dung bài forum/comment hợp lệ (published + consent_research_analysis).
2. Chuẩn hoá Unicode NFC, bóc tách từ đơn và cụm từ (n-grams).
3. Phát hiện từ ngoài từ điển (OOV) và cụm từ đặc thù.
4. Gom ngữ cảnh (Context Clustering) và ghi nhận lần xuất hiện (Occurrence).
5. Sinh giả thuyết nghĩa (CandidateSense) và cụm từ (CandidatePhrase) với điểm tin cậy độc lập.
6. Hỗ trợ Language Expert / Admin duyệt vào Master Lexicon hoặc từ chối và purge.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.db import utcnow
from ..core.deps import audit, notify, permissions_of
from ..core.errors import AppError, not_found
from ..core.text import nfc, search_key, words
from ..models import (CandidateEvidence, CandidateOccurrence, CandidatePhrase, CandidateSense,
                      ContextCluster, ForumComment, ForumPost, LexicalCandidate, LexicalEntry,
                      LexicalSense, Source, User)

WORD_PUNCT = re.compile(r"^[^\w\s]+$")


def _is_valid_token(tok: str) -> bool:
    if len(tok) < 2 or len(tok) > 40:
        return False
    if tok.isdigit() or WORD_PUNCT.match(tok):
        return False
    if tok.lower().startswith(("http", "www")):
        return False
    return True


def _generate_ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def extract_from_text(
    db: Session, text: str, content_type: str, content_id: uuid.UUID, author_id: uuid.UUID,
    topic: str = "general", dialect_id: uuid.UUID | None = None
) -> list[LexicalCandidate]:
    """Phân tích một đoạn văn bản để tìm từ/cụm từ mới và cập nhật candidate."""
    normalized_text = nfc(text)
    token_list = [w for w in words(normalized_text) if _is_valid_token(w)]
    if not token_list:
        return []

    # Lấy các từ đã biết trong Master Lexicon
    token_keys = {search_key(t) for t in token_list}
    known_keys = set(
        db.scalars(
            select(LexicalEntry.normalized_form).where(
                LexicalEntry.normalized_form.in_(token_keys),
                LexicalEntry.status == "published"
            )
        ).all()
    )

    oov_tokens = [t for t in token_list if search_key(t) not in known_keys]
    discovered = []
    author_pseudo = f"anon-{str(author_id)[:8]}"

    # Xử lý OOV từ đơn
    for tok in set(oov_tokens):
        key = search_key(tok)
        candidate = db.scalar(select(LexicalCandidate).where(LexicalCandidate.normalized_form == key))
        now = utcnow()
        if not candidate:
            candidate = LexicalCandidate(
                candidate_form=tok,
                normalized_form=key,
                language_code="ede",
                candidate_status="new",
                first_seen_at=now,
                last_seen_at=now,
            )
            db.add(candidate)
            db.flush()

            # Tạo ContextCluster mặc định
            cluster = ContextCluster(
                candidate_id=candidate.id,
                syntactic_pattern="context_in_forum",
                topic_label=topic,
                dialect_id=dialect_id,
            )
            db.add(cluster)
            db.flush()

            # Tạo giả thuyết nghĩa CandidateSense ban đầu
            sense = CandidateSense(
                candidate_id=candidate.id,
                cluster_id=cluster.id,
                proposed_definition_vi=f"(Giả thuyết nghĩa trong ngữ cảnh {topic})",
                part_of_speech_hypothesis="unknown",
                support_score=1.0,
                contradiction_score=0.0,
                context_diversity_score=1.0,
                source_independence_score=1.0,
                confidence_status="initial_hypothesis",
            )
            db.add(sense)
            db.flush()
        else:
            candidate.last_seen_at = now
            if candidate.candidate_status == "new":
                candidate.candidate_status = "collecting_evidence"

        # Kiểm tra trùng occurrence
        existing_occ = db.scalar(
            select(CandidateOccurrence).where(
                CandidateOccurrence.candidate_id == candidate.id,
                CandidateOccurrence.content_type == content_type,
                CandidateOccurrence.content_id == content_id,
            )
        )
        if not existing_occ:
            # Tìm ngữ cảnh trước/sau
            idx = normalized_text.lower().find(tok.lower())
            start = max(0, idx - 40)
            end = min(len(normalized_text), idx + len(tok) + 40)
            left_ctx = normalized_text[start:idx].strip()
            right_ctx = normalized_text[idx + len(tok):end].strip()

            occ = CandidateOccurrence(
                candidate_id=candidate.id,
                content_type=content_type,
                content_id=content_id,
                sentence_text=normalized_text[:500],
                left_context=left_ctx,
                right_context=right_ctx,
                dialect_id=dialect_id,
                author_pseudonymous_id=author_pseudo,
                source_ref=f"{content_type}:{content_id}",
            )
            db.add(occ)
            db.flush()

            # Cập nhật điểm và thêm evidence
            if candidate.senses:
                first_sense = candidate.senses[0]
                first_sense.support_score += 1.0
                first_sense.source_independence_score = float(len(
                    {o.author_pseudonymous_id for o in candidate.occurrences if o.author_pseudonymous_id}
                ))
                db.add(CandidateEvidence(
                    candidate_sense_id=first_sense.id,
                    occurrence_id=occ.id,
                    evidence_type="supports",
                    reason=f"Xuất hiện trong bài viết ngữ cảnh '{topic}'",
                    model_version="discovery-rules-v1",
                ))

        discovered.append(candidate)

    # Xử lý Cụm từ (n-grams từ 2 đến 3 từ)
    for n in (2, 3):
        ngrams = _generate_ngrams(token_list, n)
        for phrase in set(ngrams):
            pkey = search_key(phrase)
            # Chỉ lưu n-gram nếu có ít nhất 1 từ OOV hoặc cụm dài có dấu hiệu riêng
            has_oov = any(search_key(w) not in known_keys for w in phrase.split())
            if not has_oov:
                continue
            cand_phrase = db.scalar(select(CandidatePhrase).where(CandidatePhrase.normalized_phrase == pkey))
            if not cand_phrase:
                cand_phrase = CandidatePhrase(
                    phrase_text=phrase,
                    normalized_phrase=pkey,
                    phrase_type_hypothesis="phrase" if n == 2 else "collocation",
                    proposed_meaning=f"(Cụm từ phát hiện tự động trong {topic})",
                    stability_score=1.0,
                    support_score=1.0,
                    contradiction_score=0.0,
                )
                db.add(cand_phrase)
                db.flush()
            else:
                cand_phrase.support_score += 1.0
                cand_phrase.stability_score += 0.5

    db.commit()
    return discovered


def run_discovery_pipeline(db: Session, limit: int = 50) -> dict:
    """Quét các bài viết và bình luận đã public và có consent_research_analysis để tìm ứng viên."""
    posts = db.scalars(
        select(ForumPost).where(
            ForumPost.status == "published",
            ForumPost.consent_research_analysis.is_(True),
            ForumPost.deleted_at.is_(None),
        ).limit(limit)
    ).all()

    total_candidates_found = 0
    posts_processed = len(posts)

    for p in posts:
        text = f"{p.title}\n{p.body_text}"
        found = extract_from_text(db, text, "post", p.id, p.author_id, topic=p.category)
        total_candidates_found += len(found)

        # Quét các comment thuộc post này
        for c in p.comments:
            if c.status == "published" and not c.deleted_at:
                cfound = extract_from_text(db, c.body_text, "comment", c.id, c.author_id, topic=p.category)
                total_candidates_found += len(cfound)

    return {
        "posts_processed": posts_processed,
        "total_occurrences_found": total_candidates_found,
        "status": "completed",
    }


def list_candidates(db: Session, status: str = "all", cursor: str | None = None, limit: int = 30):
    stmt = select(LexicalCandidate)
    if status != "all":
        stmt = stmt.where(LexicalCandidate.candidate_status == status)
    return stmt.order_by(LexicalCandidate.last_seen_at.desc())


def candidate_view(c: LexicalCandidate, full: bool = False) -> dict:
    data = {
        "id": str(c.id),
        "candidate_form": c.candidate_form,
        "normalized_form": c.normalized_form,
        "language_code": c.language_code,
        "candidate_status": c.candidate_status,
        "occurrence_count": len(c.occurrences),
        "first_seen_at": c.first_seen_at,
        "last_seen_at": c.last_seen_at,
        "discovery_version": c.discovery_version,
    }
    if full:
        data.update({
            "clusters": [
                {
                    "id": str(cl.id),
                    "topic_label": cl.topic_label,
                    "syntactic_pattern": cl.syntactic_pattern,
                    "created_at": cl.created_at,
                }
                for cl in c.clusters
            ],
            "occurrences": [
                {
                    "id": str(o.id),
                    "content_type": o.content_type,
                    "sentence_text": o.sentence_text,
                    "left_context": o.left_context,
                    "right_context": o.right_context,
                    "author_pseudonymous_id": o.author_pseudonymous_id,
                    "observed_at": o.observed_at,
                }
                for o in c.occurrences
            ],
            "senses": [
                {
                    "id": str(s.id),
                    "proposed_definition_vi": s.proposed_definition_vi,
                    "part_of_speech_hypothesis": s.part_of_speech_hypothesis,
                    "support_score": s.support_score,
                    "contradiction_score": s.contradiction_score,
                    "context_diversity_score": s.context_diversity_score,
                    "source_independence_score": s.source_independence_score,
                    "confidence_status": s.confidence_status,
                    "status": s.status,
                    "evidences": [
                        {
                            "id": str(e.id),
                            "evidence_type": e.evidence_type,
                            "reason": e.reason,
                            "created_at": e.created_at,
                        }
                        for e in s.evidences
                    ],
                }
                for s in c.senses
            ],
            "phrases": [
                {
                    "id": str(p.id),
                    "phrase_text": p.phrase_text,
                    "phrase_type_hypothesis": p.phrase_type_hypothesis,
                    "proposed_meaning": p.proposed_meaning,
                    "support_score": p.support_score,
                    "stability_score": p.stability_score,
                }
                for p in c.phrases
            ],
        })
    return data


def approve_candidate(
    db: Session, candidate_id: uuid.UUID, reviewer: User, reason_code: str,
    definition_vi: str, part_of_speech: str | None = None,
    entry_type: str = "word", sense_id: uuid.UUID | None = None, review_note: str | None = None
) -> dict:
    """Duyệt candidate vào Master Lexicon (tạo LexicalEntry và LexicalSense)."""
    cand = db.get(LexicalCandidate, candidate_id)
    if not cand:
        raise not_found()
    if cand.candidate_status == "approved":
        raise AppError(409, "ALREADY_APPROVED", "Ứng viên này đã được duyệt.")

    is_expert = "lexicon.verify" in permissions_of(reviewer)
    now = utcnow()
    source = db.scalar(select(Source).where(Source.code == "ai_discovery"))
    if not source:
        source = db.scalar(select(Source).where(Source.code == "community"))

    # Tìm hoặc tạo LexicalEntry
    entry = db.scalar(
        select(LexicalEntry).where(
            LexicalEntry.normalized_form == cand.normalized_form,
            LexicalEntry.status == "published"
        )
    )
    if not entry:
        entry = LexicalEntry(
            canonical_form=cand.candidate_form,
            normalized_form=cand.normalized_form,
            entry_type=entry_type,
            source_id=source.id if source else None,
            source_ref=f"discovery:{cand.id}",
        )
        db.add(entry)
        db.flush()

    sense_num = max([s.sense_number for s in entry.senses], default=0) + 1
    new_sense = LexicalSense(
        entry_id=entry.id,
        sense_number=sense_num,
        definition_vi=definition_vi,
        definition_vi_key=search_key(definition_vi),
        part_of_speech=part_of_speech,
        status="verified" if is_expert else "draft",
        verification_level="language_expert" if is_expert else "admin_approved",
        verified_by=reviewer.id if is_expert else None,
        verified_at=now if is_expert else None,
        source_id=source.id if source else None,
    )
    db.add(new_sense)

    cand.candidate_status = "approved"
    if cand.senses:
        for s in cand.senses:
            if sense_id is None or s.id == sense_id:
                s.status = "approved"

    audit(db, reviewer, "lexical_candidate.approve", "lexical_candidate", cand.id, reason_code,
          entry_id=str(entry.id), verified=is_expert, note=review_note)
    db.commit()
    return {"candidate_id": str(cand.id), "entry_id": str(entry.id), "status": "approved"}


def reject_candidate(
    db: Session, candidate_id: uuid.UUID, reviewer: User, reason_code: str, review_note: str | None = None
) -> dict:
    """Từ chối candidate và purge câu nhạy cảm theo chính sách retention (docs/03 §7)."""
    cand = db.get(LexicalCandidate, candidate_id)
    if not cand:
        raise not_found()
    cand.candidate_status = "rejected"
    # Purge câu trích xuất khỏi occurrences để bảo vệ quyền riêng tư
    for occ in cand.occurrences:
        occ.sentence_text = None
        occ.left_context = None
        occ.right_context = None

    for s in cand.senses:
        s.status = "rejected"

    audit(db, reviewer, "lexical_candidate.reject", "lexical_candidate", cand.id, reason_code, note=review_note)
    db.commit()
    return {"candidate_id": str(cand.id), "status": "rejected", "purged": True}


def request_evidence(db: Session, candidate_id: uuid.UUID, reviewer: User, note: str) -> dict:
    cand = db.get(LexicalCandidate, candidate_id)
    if not cand:
        raise not_found()
    cand.candidate_status = "collecting_evidence"
    audit(db, reviewer, "lexical_candidate.request_evidence", "lexical_candidate", cand.id, note=note)
    db.commit()
    return {"candidate_id": str(cand.id), "status": cand.candidate_status}
