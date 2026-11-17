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
