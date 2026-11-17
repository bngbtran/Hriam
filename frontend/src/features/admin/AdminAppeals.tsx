import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Appeal } from "../../lib/types";

export function AdminAppeals() {
  const [status, setStatus] = useState("pending");
  const q = useQuery({ queryKey: ["admin-appeals", status], queryFn: () => api.get<Appeal[]>("/admin/appeals", { status }) });
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Khiếu nại">
        Nên do người khác với người ra quyết định ban đầu xem xét. Chấp nhận sẽ huỷ strike của quyết định đó và khôi phục nội dung.
      </PageHead>
      <div className="chips">
        {[["pending", "Chờ xử lý"], ["accepted", "Đã chấp nhận"], ["rejected", "Đã bác"], ["all", "Tất cả"]].map(([s, l]) => (
          <button key={s} className={status === s ? "on" : ""} onClick={() => setStatus(s)}>{l}</button>
        ))}
      </div>
      <ErrorBox error={q.error} />
      {q.isLoading ? <Spinner /> : !q.data?.length ? <Empty motif="rua">Không có khiếu nại.</Empty> : (
        <ul className="list">{q.data.map((a) => <AppealItem key={a.id} a={a} />)}</ul>
      )}
    </>
  );
}

function AppealItem({ a }: { a: Appeal }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const [note, setNote] = useState("");
  const decide = useMutation({
    mutationFn: (accept: boolean) => api.post(`/admin/appeals/${a.id}/${accept ? "accept" : "reject"}`, { decision_note: note }, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-appeals"] }),
  });
  return (
    <li className="list-item">
      <div className="row-between"><b>{a.user?.display_name} · {a.content_type === "post" ? "bài viết" : "bình luận"} {a.original_decision === "reject" ? "bị từ chối" : "bị gỡ"}</b><Badge status={a.status} /></div>
      <p className="muted small">Lý do ban đầu: {a.reason} · gửi {fmtDate(a.created_at)} · <Link to={`/admin/moderation?queue=rejected`}>Xem case</Link></p>
      <p>{a.appeal_text}</p>
      {a.decision_note && <p><b>Phản hồi:</b> {a.decision_note}</p>}
      {a.status === "pending" && can("appeal.decide") && (
        <div className="form">
          <label>Phản hồi cho người dùng (bắt buộc)<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <ErrorBox error={decide.error} />
          <div className="row">
            <button className="btn primary" disabled={note.length < 3 || decide.isPending} onClick={() => decide.mutate(true)}>Chấp nhận</button>
            <button className="btn ghost" disabled={note.length < 3 || decide.isPending} onClick={() => decide.mutate(false)}>Bác khiếu nại</button>
          </div>
        </div>
      )}
    </li>
  );
}
