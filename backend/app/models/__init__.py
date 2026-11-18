"""Nạp mọi model để Alembic và metadata thấy đủ bảng."""
from .account import (IdempotencyKey, Permission, PhoneVerificationCode, RefreshSession, Role, RolePermission, User,  # noqa: F401
                      UserPhoneRestriction, UserRole)
from .community import (AdminAuditLog, ContentReport, ContributionSubmission, ForumComment, ForumPost,  # noqa: F401
                        ModerationAction, ModerationCase, Notification, TranslationFeedback, TranslationRecord,
                        UserAppeal, UserStrikeEvent)
from .conversation import (ConversationParticipant, ConversationRoom, ConversationTurn)  # noqa: F401
from .culture import CulturalItem  # noqa: F401
from .discovery import (CandidateEvidence, CandidateOccurrence, CandidatePhrase, CandidateSense,  # noqa: F401
                        ContextCluster, LexicalCandidate)
from .lexicon import (CorpusExample, DatasetRelease, DatasetReleaseItem, Dialect, LexicalEntry,  # noqa: F401
                      LexicalForm, LexicalSense, License, OrthographyProfile, PhraseComponent, SenseExample, Source,
                      TranslationCorpus)

