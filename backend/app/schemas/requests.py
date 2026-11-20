"""Pydantic schema cho request (docs/07). Phản hồi bọc trong {"data", "meta"}."""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

Lang = Literal["ede", "vi"]


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=10, max_length=200)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=30)
    accept_terms: bool


class LoginIn(BaseModel):
    username: str = Field(max_length=40)
    password: str = Field(max_length=200)


class RefreshIn(BaseModel):
    refresh_token: str | None = Field(default=None, max_length=200)


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    save_translation_history: bool | None = None


class TranslateIn(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source_language: Lang | Literal["auto"] = "auto"
    target_language: Lang | None = None
    dialect_id: uuid.UUID | None = None
    context: str | None = Field(default=None, max_length=200)
    use_verified_memory: bool = True
    # Bộ dịch máy cho lần này: "local" chỉ mô hình Hriăm (không gửi dữ liệu ra ngoài); "gemini" ưu tiên Gemini
    # (lỗi thì rơi về mô hình); bỏ trống thì theo cấu hình máy chủ (MT_PROVIDER).
    engine: Literal["local", "gemini"] | None = None


class FeedbackIn(BaseModel):
    source_text: str = Field(min_length=1, max_length=5000)
    translated_text: str = Field(max_length=5000)
    source_language: Lang
    target_language: Lang
    error_type: Literal["wrong_meaning", "omission", "hallucination", "terminology", "phrase_idiom", "dialect",
                        "spelling", "other"]
    suggested_translation: str | None = Field(default=None, max_length=5000)
    comment: str | None = Field(default=None, max_length=2000)
    model_version: str | None = Field(default=None, max_length=120)
    consent_publish_as_lexicon: bool = False
    consent_research: bool = False


class Consents(BaseModel):
    publish_as_lexicon: bool = False
    use_for_research: bool = False
    use_for_model_training: bool = False


class ContributionIn(BaseModel):
    submission_type: Literal["word", "sense", "phrase", "sentence_pair", "audio", "correction"]
    ede_form: str = Field(min_length=1, max_length=2000)
    proposed_vi_meaning: str | None = Field(default=None, max_length=2000)
    context_text: str | None = Field(default=None, max_length=2000)
    phrase_type: Literal["collocation", "phrase", "verb_phrase", "idiom", "proverb", "unknown"] | None = None
    target_entry_id: uuid.UUID | None = None
    dialect_id: uuid.UUID | None = None
    source_note: str | None = Field(default=None, max_length=1000)
    consents: Consents = Consents()


class ReviewIn(BaseModel):
    reason_code: str = Field(min_length=2, max_length=60)
    review_note: str | None = Field(default=None, max_length=2000)
    definition_vi: str | None = Field(default=None, max_length=2000)
    part_of_speech: str | None = Field(default=None, max_length=60)


class PostIn(BaseModel):
    category: Literal["hoi-dap", "tu-vung", "phat-am", "phuong-ngu", "van-hoa", "hoc-tieng", "gop-y-ban-dich"]
    title: str = Field(min_length=3, max_length=200)
    body_text: str = Field(min_length=1, max_length=20000)
    consent_research_analysis: bool = False


class PostPatch(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    body_text: str | None = Field(default=None, min_length=1, max_length=20000)
    consent_research_analysis: bool | None = None


class CommentIn(BaseModel):
    body_text: str = Field(min_length=1, max_length=5000)
    parent_id: uuid.UUID | None = None


class ReportIn(BaseModel):
    reason_code: str = Field(min_length=2, max_length=60)
    note: str | None = Field(default=None, max_length=1000)
    comment_id: uuid.UUID | None = None


class DecisionIn(BaseModel):
    reason_code: str | None = Field(default=None, max_length=60)
    note: str | None = Field(default=None, max_length=2000)
    apply_strike: bool = False


class AppealIn(BaseModel):
    moderation_case_id: uuid.UUID
    appeal_text: str = Field(min_length=10, max_length=4000)


class AppealDecisionIn(BaseModel):
    decision_note: str = Field(min_length=3, max_length=2000)


class ReasonIn(BaseModel):
    reason_code: str = Field(min_length=2, max_length=60)
    note: str = Field(min_length=3, max_length=2000)


class RolesIn(BaseModel):
    roles: list[Literal["user", "trusted_contributor", "language_expert", "moderator", "admin"]]
    note: str = Field(min_length=3, max_length=500)


class ReleaseIn(BaseModel):
    version: str = Field(pattern=r"^\d{4}\.\d{2}(\.\d+)?(-[a-z0-9]+)?$")
    change_summary: str = Field(min_length=3, max_length=2000)


# ---------- Lexical Discovery ----------

class CandidateApproveIn(BaseModel):
    sense_id: uuid.UUID | None = None
    reason_code: str = Field(default="LEXICAL_DISCOVERY_APPROVED", min_length=2, max_length=60)
    review_note: str | None = Field(default=None, max_length=2000)
    canonical_form: str | None = Field(default=None, max_length=500)
    definition_vi: str = Field(min_length=1, max_length=2000)
    part_of_speech: str | None = Field(default=None, max_length=60)
    entry_type: Literal["word", "multiword_expression", "idiom", "proverb", "phrase", "other"] = "word"


class CandidateRejectIn(BaseModel):
    reason_code: str = Field(min_length=2, max_length=60)
    review_note: str | None = Field(default=None, max_length=2000)


class CandidateRequestEvidenceIn(BaseModel):
    note: str = Field(min_length=3, max_length=2000)


# ---------- Live Conversation ----------

class RoomCreateIn(BaseModel):
    mode: Literal["shared_device", "two_devices"] = "shared_device"
    language_a: Lang = "ede"
    language_b: Lang = "vi"
    endpointing_mode: Literal["push_to_talk", "auto_pause", "sentence_aware"] = "push_to_talk"
    silence_threshold_ms: int = Field(default=1500, ge=500, le=5000)
    save_audio: bool = False
    save_transcript: bool = False


class JoinTokenIn(BaseModel):
    participant_alias: str = Field(min_length=1, max_length=60)
    language_preference: Lang = "vi"


class TurnIn(BaseModel):
    speaker: Lang
    text: str = Field(min_length=1, max_length=2000)
    audio_ref: str | None = None
    sequence_no: int = 1


# ---------- Cultural Archive ----------

class CulturalItemIn(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    category: Literal["story", "song", "proverb_idiom", "history", "custom", "term", "other"] = "story"
    content_ede: str = Field(min_length=1, max_length=50000)
    content_vi: str = Field(min_length=1, max_length=50000)
    summary: str | None = Field(default=None, max_length=2000)
    storyteller_or_author: str | None = Field(default=None, max_length=200)
    dialect_id: uuid.UUID | None = None
    region: str | None = Field(default=None, max_length=200)
    access_tier: Literal["public", "community", "restricted", "private"] = "public"
    license_id: uuid.UUID | None = None
    source_ref: str | None = Field(default=None, max_length=200)
    consent_flags: dict = Field(default_factory=dict)


class CulturalItemReviewIn(BaseModel):
    approve: bool
    decision_note: str = Field(min_length=3, max_length=2000)


# ---------- Phone Verification ----------

class RequestPhoneCodeIn(BaseModel):
    phone: str = Field(min_length=8, max_length=30)


class VerifyPhoneCodeIn(BaseModel):
    code: str = Field(min_length=4, max_length=10)

