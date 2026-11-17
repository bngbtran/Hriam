"""Nạp mọi model để Alembic và metadata thấy đủ bảng."""
from .account import (IdempotencyKey, Permission, RefreshSession, Role, RolePermission, User,  # noqa: F401
                      UserPhoneRestriction, UserRole)
from .community import (AdminAuditLog, ContentReport, ContributionSubmission, ForumComment, ForumPost,  # noqa: F401
                        ModerationAction, ModerationCase, Notification, TranslationFeedback, TranslationRecord,
                        UserAppeal, UserStrikeEvent)
from .lexicon import (CorpusExample, DatasetRelease, DatasetReleaseItem, Dialect, LexicalEntry,  # noqa: F401
                      LexicalForm, LexicalSense, License, OrthographyProfile, PhraseComponent, SenseExample, Source,
                      TranslationCorpus)
