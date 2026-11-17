export type Lang = "ede" | "vi";

export interface Me {
  id: string; username: string; display_name: string; email: string | null; has_phone: boolean;
  status: "active" | "suspended" | "permanently_banned" | "deleted"; roles: string[]; permissions: string[];
  save_translation_history: boolean; effective_strikes: number; created_at: string;
}

export interface SenseHit { entry_id: string; sense_id: string; status: string; source: string | null; text: string; form: string; variant?: string }
export interface TermMatch { term: string; senses: SenseHit[]; verified: boolean }
export interface Note { code: string; message: string; terms?: string[] }
export interface Translation {
  id: string | null; source_text: string; translated_text: string; source_language: Lang; target_language: Lang;
  translation_status: "verified_memory" | "expert_verified" | "machine_draft" | "needs_review";
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
