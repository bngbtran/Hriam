import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { LexicalCandidate } from "../../lib/types";

const STATUSES = [
  ["all", "Tất cả"],
  ["new", "Mới phát hiện"],
  ["collecting_evidence", "Đang tích luỹ bằng chứng"],
  ["needs_expert", "Cần chuyên gia"],
  ["approved", "Đã duyệt"],
  ["rejected", "Đã từ chối"],
];

const REJECT_REASONS = [
  ["SPAM_OR_TYPO", "Spam hoặc lỗi gõ sai"],
  ["NOT_EDE_LANGUAGE", "Không phải tiếng Ê Đê / từ mượn không hợp lệ"],
  ["INSUFFICIENT_CONTEXT", "Không đủ ngữ cảnh để xác định nghĩa"],
  ["CONTRADICTORY_EVIDENCE", "Bằng chứng mâu thuẫn không thể dung hoà"],
  ["OUT_OF_SCOPE", "Ngoài phạm vi từ điển"],
];

export function AdminCandidates() {
  const [status, setStatus] = useState("all");
  const [selected, setSelected] = useState<string | null>(null);
  const qc = useQueryClient();
  const { can } = useAuth();

  const list = useQuery({
    queryKey: ["lexical-candidates", status],
    queryFn: () => api.page<LexicalCandidate[]>("/admin/lexical-candidates", { status }),
  });

  const runDiscovery = useMutation({
    mutationFn: () => api.post("/admin/lexical-candidates/run-discovery"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["lexical-candidates"] });
    },
  });

  const counts = list.data?.meta.counts as Record<string, number> | undefined;

  return (
    <>
      <PageHead eyebrow="Quản trị" title="Ứng viên từ/nghĩa/cụm do AI phát hiện (Giai đoạn 5)">
        Hệ thống tự động phân tích bài viết đã đăng mà người dùng cho phép phân tích ngôn ngữ.
        Mỗi ứng viên có ngữ cảnh, cụm từ và bằng chứng riêng. AI không tự ý đưa vào từ điển chính thức.
      </PageHead>

      <div className="row wrap-row row-between mt mb">
        <div className="chips">
          {STATUSES.map(([s, l]) => (
            <button key={s} className={status === s ? "on" : ""} onClick={() => { setStatus(s); setSelected(null); }}>
              {l}{counts && s in counts ? ` (${counts[s]})` : ""}
            </button>
          ))}
        </div>
        {can("lexicon.candidate_review") && (
          <button className="btn ghost" disabled={runDiscovery.isPending} onClick={() => runDiscovery.mutate()}>
            {runDiscovery.isPending ? "Đang phân tích bài viết…" : "⚡ Chạy phân tích AI ngay"}
          </button>
        )}
      </div>

      <ErrorBox error={list.error ?? runDiscovery.error} />
      {runDiscovery.data != null && (
        <p className="alert ok">
          Đã quét {String((runDiscovery.data as Record<string, unknown>).posts_processed ?? 0)} bài viết đủ điều kiện.
          Tìm thấy {String((runDiscovery.data as Record<string, unknown>).total_occurrences_found ?? 0)} lượt xuất hiện ứng viên.
        </p>
      )}

      <div className="master-detail">
        <div>
          {list.isLoading ? (
            <Spinner />
          ) : !list.data?.data.length ? (
            <Empty motif="chuon-chuon">Không có ứng viên nào.</Empty>
          ) : (
            <ul className="list selectable">
              {list.data.data.map((c) => (
                <li key={c.id}>
                  <button className={`list-item${selected === c.id ? " on" : ""}`} onClick={() => setSelected(c.id)}>
                    <span className="row-between">
                      <b lang="rad">{c.candidate_form}</b>
                      <Badge status={c.candidate_status} />
                    </span>
                    <span className="muted small">
                      {c.occurrence_count} lần xuất hiện · phát hiện {fmtDate(c.first_seen_at)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          {selected ? <CandidateDetail id={selected} /> : <p className="muted">Chọn một ứng viên để xem chi tiết.</p>}
        </div>
      </div>
    </>
  );
}

function CandidateDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["candidate-detail", id], queryFn: () => api.get<LexicalCandidate>(`/admin/lexical-candidates/${id}`) });

  const [definition, setDefinition] = useState("");
  const [pos, setPos] = useState("");
  const [entryType, setEntryType] = useState<"word" | "multiword_expression" | "idiom" | "proverb">("word");
  const [rejectReason, setRejectReason] = useState("SPAM_OR_TYPO");
  const [note, setNote] = useState("");

  const done = () => {
    qc.invalidateQueries({ queryKey: ["lexical-candidates"] });
    qc.invalidateQueries({ queryKey: ["candidate-detail", id] });
  };

  const approve = useMutation({
    mutationFn: () => api.post(`/admin/lexical-candidates/${id}/approve`, {
      definition_vi: definition,
      part_of_speech: pos || null,
      entry_type: entryType,
      reason_code: "EXPERT_VERIFIED",
      review_note: note || null,
    }, true),
    onSuccess: done,
  });

  const reject = useMutation({
    mutationFn: () => api.post(`/admin/lexical-candidates/${id}/reject`, {
      reason_code: rejectReason,
      review_note: note || null,
    }, true),
    onSuccess: done,
  });

  const requestEvidence = useMutation({
    mutationFn: () => api.post(`/admin/lexical-candidates/${id}/request-evidence`, {
      note: note || "Cần thêm ví dụ sử dụng thực tế từ cộng đồng",
    }),
    onSuccess: done,
  });

  if (q.isLoading) return <Spinner />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const c = q.data;
  const isApproved = c.candidate_status === "approved";
  const isRejected = c.candidate_status === "rejected";

  return (
    <div className="card detail">
      <div className="row-between">
        <h2 lang="rad">{c.candidate_form}</h2>
        <Badge status={c.candidate_status} />
      </div>
      <p className="muted small">Khóa tìm kiếm: <code>{c.normalized_form}</code> · Phiên bản: {c.discovery_version}</p>

      <h3>Giả thuyết nghĩa (Sense Hypotheses)</h3>
      {c.senses?.length ? (
        <ul className="list">
          {c.senses.map((s) => (
            <li key={s.id} className="list-item">
              <div className="row-between">
                <b>{s.proposed_definition_vi}</b>
                <Badge status={s.confidence_status} />
              </div>
              <p className="muted small">
                Ủng hộ: +{s.support_score} · Mâu thuẫn: -{s.contradiction_score} · Đa dạng ngữ cảnh: {s.context_diversity_score} · Độc lập nguồn: {s.source_independence_score}
              </p>
              {s.evidences && s.evidences.length > 0 && (
                <ul className="timeline mt">
                  {s.evidences.map((e) => (
                    <li key={e.id}>
                      <Badge status={e.evidence_type} /> {e.reason} ({fmtDate(e.created_at)})
                    </li>
                  ))}
                </ul>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Chưa có giả thuyết nghĩa.</p>
      )}

      {c.phrases && c.phrases.length > 0 && (
        <>
          <h3 className="mt">Cụm từ liên quan (Phrases / Collocations)</h3>
          <ul className="list">
            {c.phrases.map((p) => (
              <li key={p.id} className="list-item">
                <b lang="rad">{p.phrase_text}</b> ({p.phrase_type_hypothesis})
                <p className="muted small">Độ ổn định: {p.stability_score} · Ủng hộ: {p.support_score}</p>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="mt">Các lần xuất hiện (Occurrences: {c.occurrences?.length ?? 0})</h3>
      {c.occurrences?.length ? (
        <ul className="list">
          {c.occurrences.map((o) => (
            <li key={o.id} className="list-item">
              <p className="small">
                {o.left_context && <span className="muted">{o.left_context} </span>}
                <strong lang="rad">{c.candidate_form}</strong>
                {o.right_context && <span className="muted"> {o.right_context}</span>}
              </p>
              <p className="muted small">
                Nguồn: {o.content_type} · Tác giả ẩn danh: {o.author_pseudonymous_id} · {fmtDate(o.observed_at)}
              </p>
            </li>
          ))}
        </ul>
      ) : (
        <p className="muted">Không còn câu trích dẫn (đã purge sau khi reject hoặc rút consent).</p>
      )}

      {!isApproved && !isRejected && can("lexicon.approve") && (
        <div className="form mt">
          <h3>Thẩm định và quyết định</h3>
          <label>Nghĩa tiếng Kinh chuẩn xác
            <input value={definition} onChange={(e) => setDefinition(e.target.value)} placeholder="Nhập nghĩa để đưa vào từ điển…" />
          </label>
          <div className="two-col">
            <label>Từ loại
              <input value={pos} onChange={(e) => setPos(e.target.value)} placeholder="danh từ, động từ…" />
            </label>
            <label>Loại mục từ
              <select value={entryType} onChange={(e) => setEntryType(e.target.value as typeof entryType)}>
                <option value="word">Từ đơn</option>
                <option value="multiword_expression">Cụm từ</option>
                <option value="idiom">Thành ngữ</option>
                <option value="proverb">Tục ngữ</option>
              </select>
            </label>
          </div>
          <label>Ghi chú thẩm định
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Ghi chú cho chuyên gia / kiểm toán…" />
          </label>

          <ErrorBox error={approve.error ?? reject.error ?? requestEvidence.error} />

          <div className="row wrap-row">
            <button className="btn primary" disabled={!definition.trim() || approve.isPending} onClick={() => approve.mutate()}>
              ✓ Duyệt vào Master Lexicon
            </button>
            <button className="btn ghost" disabled={requestEvidence.isPending} onClick={() => requestEvidence.mutate()}>
              🔍 Yêu cầu thêm bằng chứng
            </button>
            <div className="row">
              <select value={rejectReason} onChange={(e) => setRejectReason(e.target.value)}>
                {REJECT_REASONS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <button className="btn danger" disabled={reject.isPending}
                onClick={() => confirm("Từ chối ứng viên này sẽ purge sạch câu trích dẫn để bảo vệ dữ liệu. Tiếp tục?") && reject.mutate()}>
                ✕ Từ chối & Purge
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
