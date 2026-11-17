import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Appeal } from "../../lib/types";

const QUEUES = [["human_review", "Chờ người duyệt"], ["reports", "Báo cáo"], ["rejected", "Đã từ chối/gỡ"], ["resolved", "Đã xử lý"]];

interface CaseRow { id: string; content_type: string; trigger: string; status: string; risk_level: string; language_detected: string | null;
  final_decision: string | null; decision_reason: string | null; created_at: string; content_status: string | null; excerpt: string }
interface CaseFull extends CaseRow {
  detector_results: Record<string, unknown>; content: { title: string | null; body_text: string | null; post_id: string | null };
  author: { id: string; username: string; display_name: string; status: string; effective_strikes: number };
  actions: { action: string; actor_type: string; reason_code: string | null; note: string | null; created_at: string }[];
  appeal: Appeal | null; reasons: Record<string, string>; policy_version: string;
}

export function AdminModeration() {
  const [params, setParams] = useSearchParams();
  const queue = params.get("queue") ?? "human_review";
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ queryKey: ["cases", queue], queryFn: () => api.page<CaseRow[]>("/admin/moderation/cases", { queue }) });
  const counts = list.data?.meta.counts as Record<string, number> | undefined;
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Kiểm duyệt">
        Nội dung tiếng Ê Đê hoặc chưa rõ được giữ ẩn để người duyệt xem. Strike chỉ áp dụng khi bạn xác nhận vi phạm.
      </PageHead>
      <div className="chips">
        {QUEUES.map(([q, l]) => (
          <button key={q} className={queue === q ? "on" : ""} onClick={() => { setParams({ queue: q }); setSelected(null); }}>
            {l}{counts && q in counts ? ` (${counts[q]})` : ""}
          </button>
        ))}
      </div>
      <ErrorBox error={list.error} />
      <div className="master-detail">
        <div>
          {list.isLoading ? <Spinner /> : !list.data?.data.length ? <Empty motif="rua">Hàng chờ trống.</Empty> : (
            <ul className="list selectable">
              {list.data.data.map((c) => (
                <li key={c.id}>
                  <button className={`list-item${selected === c.id ? " on" : ""}`} onClick={() => setSelected(c.id)}>
                    <span className="row-between"><b>{c.content_type === "post" ? "Bài viết" : "Bình luận"}{c.trigger === "report" ? " · bị báo cáo" : c.trigger === "edit" ? " · đã sửa" : ""}</b>
                      <Badge status={c.content_status ?? c.status} /></span>
                    <span className="muted small">{c.excerpt}</span>
                    <span className="muted small">{fmtDate(c.created_at)} · ngôn ngữ: {c.language_detected ?? "?"} · rủi ro: {c.risk_level}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>{selected ? <CaseDetail id={selected} /> : <p className="muted">Chọn một mục để xem chi tiết.</p>}</div>
      </div>
    </>
  );
}

function CaseDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const q = useQuery({ queryKey: ["case", id], queryFn: () => api.get<CaseFull>(`/admin/moderation/cases/${id}`) });
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [strike, setStrike] = useState(false);
  const act = useMutation({
    mutationFn: (action: string) => api.post(`/admin/moderation/cases/${id}/${action}`, { reason_code: reason || null, note: note || null, apply_strike: strike }, true),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["cases"] }); qc.invalidateQueries({ queryKey: ["case", id] }); setNote(""); },
  });
  const applyStrike = useMutation({
    mutationFn: () => api.post(`/admin/moderation/cases/${id}/apply-strike`, {}, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["case", id] }),
  });
  if (q.isLoading) return <Spinner />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const c = q.data;
  const open = c.status !== "resolved";
  return (
    <div className="card detail">
      <p className="row-between"><b>{c.content_type === "post" ? "Bài viết" : "Bình luận"}</b><Badge status={c.content_status ?? c.status} /></p>
      {c.content.title && <h3>{c.content.title}</h3>}
      <div className="post-body boxed">{c.content.body_text}</div>
      {c.content.post_id && <p className="small"><Link to={`/community/posts/${c.content.post_id}`} target="_blank">Mở bài viết</Link></p>}
      <dl className="prov">
        <div><dt>Tác giả</dt><dd>{c.author.display_name} (@{c.author.username}) · <Badge status={c.author.status} /> · {c.author.effective_strikes} strike</dd></div>
        <div><dt>Kiểm tra tự động</dt><dd>ngôn ngữ {String(c.detector_results.language_hint ?? c.language_detected ?? "?")}, {String(c.detector_results.links ?? 0)} liên kết
          {Array.isArray(c.detector_results.term_hits) && c.detector_results.term_hits.length > 0 && `, khớp: ${(c.detector_results.term_hits as string[]).join(", ")}`}
          {c.detector_results.reports ? `, ${String(c.detector_results.reports)} báo cáo` : ""} · chính sách {c.policy_version}</dd></div>
        {c.final_decision && <div><dt>Quyết định</dt><dd>{c.final_decision} {c.decision_reason && `· ${c.reasons[c.decision_reason] ?? c.decision_reason}`}</dd></div>}
      </dl>
      <h4>Lịch sử</h4>
      <ul className="timeline">{c.actions.map((a, i) => <li key={i}>{fmtDate(a.created_at)} · {a.actor_type === "system" ? "Hệ thống" : "Người"}: {a.action}{a.reason_code && ` (${a.reason_code})`}{a.note && ` — ${a.note}`}</li>)}</ul>
      {c.appeal && <p className="alert info">Khiếu nại: <Badge status={c.appeal.status} /> {c.appeal.appeal_text}</p>}
      {can("moderation.decide") && (
        <div className="form">
          <label>Mã lý do (bắt buộc khi từ chối/gỡ)
            <select value={reason} onChange={(e) => setReason(e.target.value)}>
              <option value="">— Chọn —</option>
              {Object.entries(c.reasons).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </label>
          <label>Ghi chú cho người dùng / nội bộ<input value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} /></label>
          {can("user.strike") && <label className="check"><input type="checkbox" checked={strike} onChange={(e) => setStrike(e.target.checked)} /> Xác nhận vi phạm và tính 1 strike</label>}
          <ErrorBox error={act.error ?? applyStrike.error} />
          <div className="row wrap-row">
            {(open || c.content_status !== "published") && <button className="btn primary" disabled={act.isPending} onClick={() => act.mutate("approve")}>Cho đăng</button>}
            {open && <button className="btn danger" disabled={!reason || act.isPending} onClick={() => act.mutate("reject")}>Từ chối</button>}
            {c.content_status === "published" && <button className="btn danger" disabled={!reason || act.isPending} onClick={() => act.mutate("remove")}>Gỡ bài</button>}
            {open && <button className="btn ghost" disabled={!note || act.isPending} onClick={() => act.mutate("ask-context")}>Hỏi thêm ngữ cảnh</button>}
            {!open && can("user.strike") && ["reject", "remove"].includes(c.final_decision ?? "") &&
              <button className="btn ghost" onClick={() => applyStrike.mutate()}>Áp dụng strike</button>}
          </div>
          {applyStrike.data != null && <p className="muted small">{(applyStrike.data as { applied: boolean }).applied ? "Đã áp dụng strike." : "Case này đã có strike."}</p>}
        </div>
      )}
    </div>
  );
}
