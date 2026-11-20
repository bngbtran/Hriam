export type Lang = "ede" | "vi";

export interface Me {
  id: string; username: string; display_name: string; email: string | null; has_phone: boolean; phone_verified?: boolean;
  status: "active" | "suspended" | "permanently_banned" | "deleted"; roles: string[]; permissions: string[];
  save_translation_history: boolean; effective_strikes: number; created_at: string;
}

export interface SenseHit { entry_id: string; sense_id: string; status: string; source: string | null; text: string; form: string; variant?: string }
export interface TermMatch { term: string; senses: SenseHit[]; verified: boolean }
export interface Note { code: string; message: string; terms?: string[] }
export interface Translation {
  id: string | null; source_text: string; translated_text: string; source_language: Lang; target_language: Lang;
  translation_status: "verified_memory" | "expert_verified" | "dictionary_example" | "machine_draft" | "needs_review";
  verified_matches: TermMatch[]; lexicon_matches: TermMatch[]; uncertainty_notes: Note[];
  similar_examples: { ede: string; vi: string; exact: boolean; verification_status: string }[];
  model_version: string | null; provenance: Record<string, unknown>; seconds: number; detected_language: Lang | null;
}

export interface EntrySummary {
  id: string; canonical_form: string; entry_type: string; part_of_speech: string | null; status: string;
  senses: { id: string; sense_number: number; definition_vi: string; status: string }[]; variants: string[];
}
export interface EntryDetail extends Omit<EntrySummary, "senses"> {
  language_code: string; loan_source: string | null; notes: string;
  forms: { form_text: string; form_type: string; is_preferred: boolean; notes: string }[];
  senses: {
    id: string; sense_number: number; definition_vi: string; definition_ede: string | null; part_of_speech: string | null;
    semantic_domain: string | null; usage_register: string | null; literal_or_figurative: string | null; status: string;
    verification_level: string; verified_at: string | null;
    examples: { ede: string; vi: string; role: string; verification_status: string }[];
  }[];
  provenance: { source: { code: string; name: string; reference: string } | null; source_ref: string | null;
    license: { name: string; review_status: string } | null; updated_at: string };
}

export interface Profile { id: string; code: string; name: string; version: string; status: string; description: string;
  characters: { char: string; upper: string; name: string; note: string }[] }

export type ContentStatus = "draft" | "pending_moderation" | "pending_human_review" | "published" | "rejected" | "removed";
export interface Post {
  id: string; category: string; category_label: string; title: string; body_text: string; author: string;
  language_hint: string | null; status: ContentStatus; published_at: string | null; created_at: string; comment_count: number | null;
  consent_research_analysis?: boolean; is_author?: boolean;
  comments?: { id: string; parent_id: string | null; body_text: string; author: string; status: ContentStatus; created_at: string; is_author: boolean }[];
}

export interface Contribution {
  id: string; submission_type: string; status: string; ede_form: string | null; proposed_vi_meaning: string | null;
  context_text: string | null; phrase_type: string | null; source_note: string | null; decision_code: string | null;
  decision_note: string | null; purged: boolean; created_at: string; reviewed_at: string | null; result_entry_id: string | null;
  consents: { publish_as_lexicon: boolean; use_for_research: boolean; use_for_model_training: boolean };
  duplicates?: { entries: { id: string; canonical_form: string; senses: string[] }[]; pending: number };
  submitter?: { id: string; username: string; display_name: string } | null;
}

export interface Appeal {
  id: string; moderation_case_id: string; appeal_text: string; status: string; decision_note: string | null; created_at: string;
  decided_at: string | null; content_type: string | null; content_id: string | null; original_decision: string | null;
  reason_code: string | null; reason: string | null; user?: { id: string; username: string; display_name: string };
}

export interface Notification { id: string; kind: string; title: string; body: string; link: string | null; read: boolean; created_at: string }

// ---------- Lexical Discovery ----------
export interface CandidateSense {
  id: string; proposed_definition_vi: string; part_of_speech_hypothesis: string | null;
  support_score: number; contradiction_score: number; context_diversity_score: number;
  source_independence_score: number; confidence_status: string; status: string;
  evidences?: { id: string; evidence_type: string; reason: string; created_at: string }[];
}
export interface CandidatePhrase {
  id: string; phrase_text: string; phrase_type_hypothesis: string; proposed_meaning: string | null;
  support_score: number; stability_score: number;
}
export interface LexicalCandidate {
  id: string; candidate_form: string; normalized_form: string; language_code: string;
  candidate_status: string; occurrence_count: number; first_seen_at: string; last_seen_at: string;
  discovery_version: string;
  clusters?: { id: string; topic_label: string; syntactic_pattern: string; created_at: string }[];
  occurrences?: { id: string; content_type: string; sentence_text: string | null; left_context: string | null; right_context: string | null; author_pseudonymous_id: string | null; observed_at: string }[];
  senses?: CandidateSense[];
  phrases?: CandidatePhrase[];
}

// ---------- Live Conversation ----------
export interface ConversationRoom {
  id: string; room_code: string; mode: "shared_device" | "two_devices";
  language_a: Lang; language_b: Lang; endpointing_mode: "push_to_talk" | "auto_pause" | "sentence_aware";
  silence_threshold_ms: number; status: string; expires_at: string; save_audio: boolean;
  save_transcript: boolean; participant_count: number; created_at: string;
}
export interface ConversationTurnItem {
  turn_id: string; sequence_no: number; speaker: Lang; target_language: Lang;
  original_text: string; translated_text: string; translation_status: string;
  model_version: string | null; seconds: number; started_at: string; ended_at: string;
}

// ---------- Cultural Archive ----------
export interface CulturalItem {
  id: string; title: string; category: string; category_label: string; summary: string | null;
  storyteller_or_author: string | null; region: string | null; access_tier: "public" | "community" | "restricted" | "private";
  status: string; content_ede?: string; content_vi?: string; source_ref?: string | null;
  consent_flags?: Record<string, boolean>; created_at: string; updated_at: string; is_author?: boolean;
}

