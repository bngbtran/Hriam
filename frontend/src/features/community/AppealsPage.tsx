import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import type { Appeal } from "../../lib/types";

interface Data {
  appeals: Appeal[];
  appealable: { case_id: string; content_type: string; decision: string; reason: string | null; decided_at: string | null }[];
}

export function AppealsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["my-appeals"], queryFn: () => api.get<Data>("/appeals/mine") });
  const strikes = useQuery({ queryKey: ["my-strikes"], queryFn: () => api.get<{ effective_strikes: number; ban_threshold: number; status: string }>("/me/strikes") });
  const [open, setOpen] = useState<string | null>(null);
  const [text, setText] = useState("");
  const send = useMutation({
    mutationFn: () => api.post("/appeals", { moderation_case_id: open, appeal_text: text }),
    onSuccess: () => { setOpen(null); setText(""); qc.invalidateQueries({ queryKey: ["my-appeals"] }); },
  });
  return (
    <div className="wrap page narrow">
      <PageHead eyebrow="Cộng đồng" title="Khiếu nại">
        Nếu cho rằng quyết định từ chối hoặc gỡ nội dung chưa đúng, hãy gửi khiếu nại. Khiếu nại được chấp nhận sẽ huỷ strike tương ứng.
      </PageHead>
      {strikes.data && (
        <p className="alert info">Strike hiệu lực: <b>{strikes.data.effective_strikes}</b>. Tài khoản bị khoá khi vượt quá {strikes.data.ban_threshold} strike.</p>
      )}
      <ErrorBox error={q.error} />
      {q.isLoading ? <Spinner /> : (
        <>
          <h2>Quyết định có thể khiếu nại</h2>
          {q.data?.appealable.length ? (
            <ul className="list">
              {q.data.appealable.map((c) => (
                <li key={c.case_id} className="list-item">
                  <div>
                    <b>{c.content_type === "post" ? "Bài viết" : "Bình luận"}</b> {c.decision === "reject" ? "bị từ chối" : "bị gỡ"} · {c.reason} · {fmtDate(c.decided_at)}
                  </div>
                  {open === c.case_id ? (
                    <form className="form" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
                      <label>Lý do khiếu nại (ít nhất 10 ký tự)
                        <textarea rows={4} value={text} maxLength={4000} onChange={(e) => setText(e.target.value)} />
                      </label>
                      <ErrorBox error={send.error} />
                      <div className="row"><button className="btn primary" disabled={text.trim().length < 10 || send.isPending}>Gửi khiếu nại</button>
                        <button type="button" className="btn ghost" onClick={() => setOpen(null)}>Huỷ</button></div>
                    </form>
                  ) : <button className="btn ghost" onClick={() => setOpen(c.case_id)}>Khiếu nại</button>}
                </li>
              ))}
            </ul>
          ) : <Empty motif="rua">Không có quyết định nào cần khiếu nại.</Empty>}
          <h2 className="mt">Khiếu nại đã gửi</h2>
          {q.data?.appeals.length ? (
            <ul className="list">
              {q.data.appeals.map((a) => (
                <li key={a.id} className="list-item">
                  <div><Badge status={a.status} /> {a.content_type === "post" ? "Bài viết" : "Bình luận"} · {a.reason} · gửi {fmtDate(a.created_at)}</div>
                  <p className="muted">{a.appeal_text}</p>
                  {a.decision_note && <p><b>Phản hồi:</b> {a.decision_note}</p>}
                </li>
              ))}
            </ul>
          ) : <p className="empty">Chưa gửi khiếu nại nào.</p>}
        </>
      )}
    </div>
  );
}
