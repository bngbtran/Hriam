import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, ErrorBox, LoginPrompt, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Post } from "../../lib/types";

const REPORT_REASONS = [["SPAM", "Spam, lừa đảo"], ["HARASSMENT", "Quấy rối"], ["HATE", "Thù ghét, phân biệt"],
  ["PERSONAL_DATA", "Lộ thông tin cá nhân"], ["COPYRIGHT", "Vi phạm bản quyền"], ["MISLEADING", "Sai lệch, giả mạo"], ["OFF_TOPIC", "Lạc chủ đề"]];

export function PostPage() {
  const { postId } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["post", postId, user?.id], queryFn: () => api.get<Post>(`/forum/posts/${postId}`) });
  const [body, setBody] = useState("");
  const [reporting, setReporting] = useState<string | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);
  const comment = useMutation({
    mutationFn: () => api.post<{ status: string }>(`/forum/posts/${postId}/comments`, { body_text: body }),
    onSuccess: () => { setBody(""); qc.invalidateQueries({ queryKey: ["post", postId] }); },
  });
  const del = useMutation({ mutationFn: () => api.del(`/forum/posts/${postId}`), onSuccess: () => nav("/community/my-submissions") });
  if (q.isLoading) return <div className="wrap page"><Spinner /></div>;
  if (!q.data) return <div className="wrap page"><ErrorBox error={q.error} /></div>;
  const p = q.data;
  return (
    <div className="wrap page narrow">
      <p><Link to="/community">← Cộng đồng</Link></p>
      <article className="card post">
        <p className="eyebrow dark">{p.category_label}</p>
        <h1 className="post-title">{p.title}</h1>
        <p className="muted small">{p.author} · {fmtDate(p.published_at ?? p.created_at)} {p.status !== "published" && <Badge status={p.status} />}</p>
        <div className="post-body">{p.body_text}</div>
        <div className="row">
          {p.is_author && <button className="btn ghost danger" onClick={() => confirm("Xoá bài viết này?") && del.mutate()}>Xoá bài</button>}
          {user && !p.is_author && p.status === "published" && <button className="link" onClick={() => setReporting("post")}>Báo cáo bài viết</button>}
        </div>
        {reporting === "post" && <ReportForm postId={p.id} onDone={() => setReporting(null)} />}
      </article>
      <section className="block">
        <h2>Bình luận ({p.comments?.filter((c) => c.status === "published").length ?? 0})</h2>
        <ul className="comments">
          {p.comments?.map((c) => (
            <li key={c.id} className="comment">
              <p className="muted small">{c.author} · {fmtDate(c.created_at)} {c.status !== "published" && <Badge status={c.status} />}</p>
              <p className="comment-body">{c.body_text}</p>
              {user && !c.is_author && c.status === "published" && <button className="link small" onClick={() => setReporting(c.id)}>Báo cáo</button>}
              {reporting === c.id && <ReportForm postId={p.id} commentId={c.id} onDone={() => setReporting(null)} />}
            </li>
          ))}
        </ul>
        {p.status !== "published" ? null : user ? (
          <form className="form" onSubmit={(e) => { e.preventDefault(); comment.mutate(); }}>
            <label htmlFor="cmt">Viết bình luận</label>
            <textarea id="cmt" ref={ref} rows={3} value={body} maxLength={5000} onChange={(e) => setBody(e.target.value)} />
            <EdeKeyboard target={ref} onChange={setBody} compact />
            <ErrorBox error={comment.error} />
            {comment.data && comment.data.status !== "published" && <p className="alert info">Bình luận đang chờ kiểm duyệt, sẽ hiện khi được duyệt.</p>}
            <button className="btn primary" disabled={!body.trim() || comment.isPending}>Gửi bình luận</button>
          </form>
        ) : <LoginPrompt action="bình luận" />}
      </section>
    </div>
  );
}

function ReportForm({ postId, commentId, onDone }: { postId: string; commentId?: string; onDone: () => void }) {
  const [reason, setReason] = useState("SPAM");
  const [note, setNote] = useState("");
  const send = useMutation({ mutationFn: () => api.post(`/forum/posts/${postId}/report`, { reason_code: reason, note: note || null, comment_id: commentId ?? null }) });
  if (send.isSuccess) return <p className="alert ok">Đã gửi báo cáo. Người kiểm duyệt sẽ xem xét. <button className="link" onClick={onDone}>Đóng</button></p>;
  return (
    <form className="form inline-form" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
      <label>Lý do<select value={reason} onChange={(e) => setReason(e.target.value)}>{REPORT_REASONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
      <label>Ghi chú<input value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} /></label>
      <ErrorBox error={send.error} />
      <div className="row"><button className="btn primary" disabled={send.isPending}>Gửi báo cáo</button><button type="button" className="btn ghost" onClick={onDone}>Huỷ</button></div>
    </form>
  );
}
