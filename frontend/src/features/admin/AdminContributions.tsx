import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Contribution } from "../../lib/types";

const TYPES: Record<string, string> = { word: "Từ mới", sense: "Nghĩa khác", phrase: "Cụm từ", sentence_pair: "Cặp câu", correction: "Sửa lỗi", audio: "Âm thanh" };
const REJECT = [["DUPLICATE", "Trùng mục đã có"], ["INSUFFICIENT_EVIDENCE", "Chưa đủ bằng chứng"], ["WRONG_MEANING", "Sai nghĩa"],
  ["SPELLING", "Sai chính tả theo chuẩn đang dùng"], ["OUT_OF_SCOPE", "Ngoài phạm vi"], ["NO_RIGHTS", "Không rõ quyền sử dụng"]];

export function AdminContributions() {
  const [status, setStatus] = useState("pending");
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["admin-contributions", status], queryFn: () => api.get<Contribution[]>("/admin/contributions", { status }) });
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Đóng góp chờ duyệt">
        Duyệt sẽ tạo/cập nhật mục từ trong Master Lexicon. Nghĩa chỉ được đánh dấu “Đã xác minh” khi người duyệt là chuyên gia ngôn ngữ.
        Từ chối sẽ xoá nội dung đóng góp.
      </PageHead>
      <div className="chips">
        {[["pending", "Chờ duyệt"], ["approved", "Đã duyệt"], ["rejected", "Đã từ chối"], ["all", "Tất cả"]].map(([s, l]) => (
          <button key={s} className={status === s ? "on" : ""} onClick={() => { setStatus(s); setSelected(null); }}>{l}</button>
        ))}
      </div>
      <ErrorBox error={list.error} />
      <div className="master-detail">
        <div>
          {list.isLoading ? <Spinner /> : !list.data?.length ? <Empty motif="than-lan">Không có đóng góp.</Empty> : (
            <ul className="list selectable">
              {list.data.map((c) => (
                <li key={c.id}>
                  <button className={`list-item${selected === c.id ? " on" : ""}`} onClick={() => setSelected(c.id)}>
                    <span className="row-between"><b lang="rad">{c.ede_form ?? "(đã xoá)"}</b><Badge status={c.status} /></span>
                    <span className="muted small">{TYPES[c.submission_type]} · {c.proposed_vi_meaning} · {c.submitter?.display_name} · {fmtDate(c.created_at)}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>{selected ? <ContributionDetail id={selected} /> : <p className="muted">Chọn một đóng góp để xem.</p>}</div>
      </div>
    </>
  );
}

function ContributionDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["admin-contribution", id], queryFn: () => api.get<Contribution>(`/admin/contributions/${id}`) });
  const [meaning, setMeaning] = useState<string | null>(null);
  const [pos, setPos] = useState("");
  const [note, setNote] = useState("");
  const [reject, setReject] = useState("DUPLICATE");
  const done = () => { qc.invalidateQueries({ queryKey: ["admin-contributions"] }); qc.invalidateQueries({ queryKey: ["admin-contribution", id] }); };
  const approve = useMutation({ mutationFn: () => api.post(`/admin/contributions/${id}/approve`, { reason_code: "APPROVED", review_note: note || null, definition_vi: meaning || null, part_of_speech: pos || null }, true), onSuccess: done });
  const rej = useMutation({ mutationFn: () => api.post(`/admin/contributions/${id}/reject`, { reason_code: reject, review_note: note || null }, true), onSuccess: done });
  if (q.isLoading) return <Spinner />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const c = q.data;
  const open = c.status === "pending" || c.status === "in_review";
  return (
    <div className="card detail">
      <p className="row-between"><b>{TYPES[c.submission_type]}</b><Badge status={c.status} /></p>
      <h3 lang="rad">{c.ede_form ?? "(nội dung đã xoá)"}</h3>
      <dl className="prov">
        <div><dt>Nghĩa đề xuất</dt><dd>{c.proposed_vi_meaning ?? "—"}</dd></div>
        {c.context_text && <div><dt>Ví dụ/ngữ cảnh</dt><dd>{c.context_text}</dd></div>}
        {c.phrase_type && <div><dt>Loại cụm</dt><dd>{c.phrase_type}</dd></div>}
        {c.source_note && <div><dt>Nguồn</dt><dd>{c.source_note}</dd></div>}
        <div><dt>Người gửi</dt><dd>{c.submitter?.display_name ?? "—"} · {fmtDate(c.created_at)}</dd></div>
        <div><dt>Đồng ý</dt><dd>{[c.consents.publish_as_lexicon && "công bố", c.consents.use_for_research && "nghiên cứu", c.consents.use_for_model_training && "huấn luyện"].filter(Boolean).join(", ") || "không"}</dd></div>
      </dl>
      {c.duplicates && (c.duplicates.entries.length > 0 || c.duplicates.pending > 0) && (
        <div className="alert warn">
          Có thể trùng: {c.duplicates.entries.map((e) => <Link key={e.id} to={`/dictionary/${e.id}`} target="_blank"> {e.canonical_form} ({e.senses.join("; ")})</Link>)}
          {c.duplicates.pending > 0 && ` · ${c.duplicates.pending} đóng góp tương tự đang chờ`}
        </div>
      )}
      {!c.consents.publish_as_lexicon && open && <p className="alert warn">Người gửi chưa đồng ý công bố, không thể duyệt vào từ điển.</p>}
      {open && (
        <div className="form">
          {c.submission_type !== "sentence_pair" && <>
            <label>Nghĩa sẽ lưu (sửa nếu cần)<input value={meaning ?? c.proposed_vi_meaning ?? ""} onChange={(e) => setMeaning(e.target.value)} /></label>
            <label>Từ loại<input value={pos} onChange={(e) => setPos(e.target.value)} placeholder="dt, đgt, tt…" /></label>
          </>}
          <label>Ghi chú duyệt<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          {!can("lexicon.verify") && <p className="muted small">Bạn không phải chuyên gia ngôn ngữ: nghĩa được duyệt sẽ ở trạng thái “Chưa xác minh”.</p>}
          <ErrorBox error={approve.error ?? rej.error} />
          <div className="row wrap-row">
            {can("lexicon.approve") && <button className="btn primary" disabled={approve.isPending || !c.consents.publish_as_lexicon} onClick={() => approve.mutate()}>Duyệt</button>}
            {can("lexicon.reject") && <>
              <select value={reject} onChange={(e) => setReject(e.target.value)} aria-label="Lý do từ chối">{REJECT.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <button className="btn danger" disabled={rej.isPending} onClick={() => confirm("Từ chối sẽ xoá nội dung đóng góp. Tiếp tục?") && rej.mutate()}>Từ chối</button>
            </>}
          </div>
        </div>
      )}
      {c.result_entry_id && <p><Link to={`/dictionary/${c.result_entry_id}`}>Xem mục từ</Link></p>}
    </div>
  );
}
