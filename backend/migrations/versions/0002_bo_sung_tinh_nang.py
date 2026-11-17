"""bo sung tinh nang: discovery, conversation, culture, phone verification

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17 23:25:00.000000
"""
from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. phone_verification_codes
    op.create_table(
        'phone_verification_codes',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('phone_hmac', sa.String(length=128), nullable=False),
        sa.Column('phone_display_masked', sa.String(length=20), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('phone_verification_codes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_phone_verification_codes_phone_hmac'), ['phone_hmac'], unique=False)
        batch_op.create_index(batch_op.f('ix_phone_verification_codes_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_phone_verification_codes_expires_at'), ['expires_at'], unique=False)

    # 2. lexical_candidates
    op.create_table(
        'lexical_candidates',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_form', sa.Text(), nullable=False),
        sa.Column('normalized_form', sa.Text(), nullable=False),
        sa.Column('language_code', sa.String(length=10), nullable=False, server_default='ede'),
        sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('candidate_status', sa.String(length=30), nullable=False, server_default='new'),
        sa.Column('discovery_version', sa.String(length=30), nullable=False, server_default='discovery-v1'),
        sa.Column('source_scope', sa.String(length=60), nullable=False, server_default='forum_published'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('lexical_candidates', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lexical_candidates_normalized_form'), ['normalized_form'], unique=False)
        batch_op.create_index(batch_op.f('ix_lexical_candidates_candidate_status'), ['candidate_status'], unique=False)
        batch_op.create_index(batch_op.f('ix_lexical_candidates_language_code'), ['language_code'], unique=False)

    # 3. candidate_occurrences
    op.create_table(
        'candidate_occurrences',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=False),
        sa.Column('content_type', sa.String(length=20), nullable=False),
        sa.Column('content_id', sa.Uuid(), nullable=False),
        sa.Column('sentence_text', sa.Text(), nullable=True),
        sa.Column('left_context', sa.Text(), nullable=True),
        sa.Column('right_context', sa.Text(), nullable=True),
        sa.Column('dialect_id', sa.Uuid(), nullable=True),
        sa.Column('author_pseudonymous_id', sa.String(length=64), nullable=True),
        sa.Column('source_ref', sa.String(length=120), nullable=True),
        sa.Column('observed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['lexical_candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dialect_id'], ['dialects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('candidate_occurrences', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_occurrences_candidate_id'), ['candidate_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_occurrences_content_id'), ['content_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_occurrences_author_pseudonymous_id'), ['author_pseudonymous_id'], unique=False)

    # 4. context_clusters
    op.create_table(
        'context_clusters',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=False),
        sa.Column('cluster_version', sa.String(length=20), nullable=False, server_default='cluster-v1'),
        sa.Column('syntactic_pattern', sa.String(length=120), nullable=True),
        sa.Column('topic_label', sa.String(length=80), nullable=True),
        sa.Column('dialect_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_id'], ['lexical_candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dialect_id'], ['dialects.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('context_clusters', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_context_clusters_candidate_id'), ['candidate_id'], unique=False)

    # 5. candidate_senses
    op.create_table(
        'candidate_senses',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=False),
        sa.Column('cluster_id', sa.Uuid(), nullable=True),
        sa.Column('proposed_definition_vi', sa.Text(), nullable=False),
        sa.Column('proposed_definition_ede', sa.Text(), nullable=True),
        sa.Column('part_of_speech_hypothesis', sa.String(length=60), nullable=True),
        sa.Column('support_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('contradiction_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('context_diversity_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('source_independence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('expert_validation_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('confidence_version', sa.String(length=20), nullable=False, server_default='score-v1'),
        sa.Column('confidence_status', sa.String(length=40), nullable=False, server_default='moderate_evidence'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='hypothesis'),
        sa.ForeignKeyConstraint(['candidate_id'], ['lexical_candidates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['context_clusters.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('candidate_senses', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_senses_candidate_id'), ['candidate_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_senses_cluster_id'), ['cluster_id'], unique=False)

    # 6. candidate_phrases
    op.create_table(
        'candidate_phrases',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=True),
        sa.Column('phrase_text', sa.Text(), nullable=False),
        sa.Column('normalized_phrase', sa.Text(), nullable=False),
        sa.Column('phrase_type_hypothesis', sa.String(length=40), nullable=False, server_default='unknown'),
        sa.Column('proposed_meaning', sa.Text(), nullable=True),
        sa.Column('compositionality_assessment', sa.String(length=60), nullable=True),
        sa.Column('stability_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('support_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('contradiction_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='hypothesis'),
        sa.ForeignKeyConstraint(['candidate_id'], ['lexical_candidates.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('candidate_phrases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_phrases_normalized_phrase'), ['normalized_phrase'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_phrases_candidate_id'), ['candidate_id'], unique=False)

    # 7. candidate_evidence
    op.create_table(
        'candidate_evidence',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('candidate_sense_id', sa.Uuid(), nullable=True),
        sa.Column('candidate_phrase_id', sa.Uuid(), nullable=True),
        sa.Column('occurrence_id', sa.Uuid(), nullable=True),
        sa.Column('evidence_type', sa.String(length=20), nullable=False, server_default='supports'),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('model_version', sa.String(length=60), nullable=False, server_default='discovery-rules-v1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['candidate_sense_id'], ['candidate_senses.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['candidate_phrase_id'], ['candidate_phrases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['occurrence_id'], ['candidate_occurrences.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('candidate_evidence', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_candidate_evidence_candidate_sense_id'), ['candidate_sense_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_candidate_evidence_candidate_phrase_id'), ['candidate_phrase_id'], unique=False)

    # 8. conversation_rooms
    op.create_table(
        'conversation_rooms',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_code', sa.String(length=16), nullable=False),
        sa.Column('room_code_hash', sa.String(length=64), nullable=False),
        sa.Column('mode', sa.String(length=30), nullable=False, server_default='shared_device'),
        sa.Column('language_a', sa.String(length=10), nullable=False, server_default='ede'),
        sa.Column('language_b', sa.String(length=10), nullable=False, server_default='vi'),
        sa.Column('endpointing_mode', sa.String(length=30), nullable=False, server_default='push_to_talk'),
        sa.Column('silence_threshold_ms', sa.Integer(), nullable=False, server_default='1500'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('save_audio_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('save_transcript_enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('room_code')
    )
    with op.batch_alter_table('conversation_rooms', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversation_rooms_room_code'), ['room_code'], unique=True)
        batch_op.create_index(batch_op.f('ix_conversation_rooms_room_code_hash'), ['room_code_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversation_rooms_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_conversation_rooms_expires_at'), ['expires_at'], unique=False)

    # 9. conversation_participants
    op.create_table(
        'conversation_participants',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('participant_alias', sa.String(length=60), nullable=False),
        sa.Column('language_preference', sa.String(length=10), nullable=False, server_default='vi'),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('left_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['room_id'], ['conversation_rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conversation_participants', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversation_participants_room_id'), ['room_id'], unique=False)

    # 10. conversation_turns
    op.create_table(
        'conversation_turns',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('room_id', sa.Uuid(), nullable=False),
        sa.Column('participant_id', sa.Uuid(), nullable=True),
        sa.Column('sequence_no', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('input_language', sa.String(length=10), nullable=False),
        sa.Column('audio_ref', sa.String(length=255), nullable=True),
        sa.Column('transcript_draft', sa.Text(), nullable=True),
        sa.Column('transcript_final', sa.Text(), nullable=False),
        sa.Column('translated_text', sa.Text(), nullable=False),
        sa.Column('translation_model_version', sa.String(length=120), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='completed'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['participant_id'], ['conversation_participants.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['room_id'], ['conversation_rooms.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('conversation_turns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_conversation_turns_room_id'), ['room_id'], unique=False)

    # 11. cultural_items
    op.create_table(
        'cultural_items',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=40), nullable=False, server_default='story'),
        sa.Column('content_ede', sa.Text(), nullable=False),
        sa.Column('content_vi', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('storyteller_or_author', sa.String(length=200), nullable=True),
        sa.Column('dialect_id', sa.Uuid(), nullable=True),
        sa.Column('region', sa.String(length=200), nullable=True),
        sa.Column('access_tier', sa.String(length=20), nullable=False, server_default='public'),
        sa.Column('license_id', sa.Uuid(), nullable=True),
        sa.Column('source_ref', sa.String(length=200), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='published'),
        sa.Column('consent_flags', sa.JSON(), nullable=False),
        sa.Column('submitted_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_by', sa.Uuid(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('decision_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['dialect_id'], ['dialects.id']),
        sa.ForeignKeyConstraint(['license_id'], ['licenses.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.ForeignKeyConstraint(['submitted_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('cultural_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_cultural_items_access_tier'), ['access_tier'], unique=False)
        batch_op.create_index(batch_op.f('ix_cultural_items_status'), ['status'], unique=False)


def downgrade() -> None:
    op.drop_table('cultural_items')
    op.drop_table('conversation_turns')
    op.drop_table('conversation_participants')
    op.drop_table('conversation_rooms')
    op.drop_table('candidate_evidence')
    op.drop_table('candidate_phrases')
    op.drop_table('candidate_senses')
    op.drop_table('context_clusters')
    op.drop_table('candidate_occurrences')
    op.drop_table('lexical_candidates')
    op.drop_table('phone_verification_codes')
