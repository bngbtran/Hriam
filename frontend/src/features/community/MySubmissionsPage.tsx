import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import type { Post } from "../../lib/types";

type Mod = { case_id: string; decision: string | null; reason_code: string | null; reason: string | null } | null;
interface Data {
  posts: (Post & { moderation: Mod })[];
  comments: { id: string; post_id: string; body_text: string; status: string; created_at: string; moderation: Mod }[];
}

export function MySubmissionsPage() {
  const q = useQuery({ queryKey: ["my-submissions"], queryFn: () => api.get<Data>("/forum/my-submissions") });
  return (
    <div className="wrap page narrow">
      <PageHead eyebrow="Cộng đồng" title="Bài và bình luận của tôi">Trạng thái kiểm duyệt của nội dung bạn đã gửi.</PageHead>
      <ErrorBox error={q.error} />
      {q.isLoading ? <Spinner /> : (
        <>
          <h2>Bài viết</h2>
          {q.data?.posts.length ? (
            <table className="table">
              <thead><tr><th>Tiêu đề</th><th>Trạng thái</th><th>Lý do</th><th>Ngày gửi</th></tr></thead>
              <tbody>{q.data.posts.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/community/posts/${p.id}`}>{p.title}</Link></td>
                  <td><Badge status={p.status} /></td>
                  <td>{p.moderation?.reason ?? "—"}{(p.status === "rejected" || p.status === "removed") && <> · <Link to="/community/appeals">Khiếu nại</Link></>}</td>
                  <td>{fmtDate(p.created_at)}</td>
                </tr>))}
              </tbody>
            </table>
          ) : <Empty>Bạn chưa viết bài nào. <Link to="/community/new">Viết bài</Link></Empty>}
          <h2 className="mt">Bình luận</h2>
          {q.data?.comments.length ? (
            <table className="table">
              <thead><tr><th>Nội dung</th><th>Trạng thái</th><th>Lý do</th><th>Ngày gửi</th></tr></thead>
              <tbody>{q.data.comments.map((c) => (
                <tr key={c.id}>
                  <td><Link to={`/community/posts/${c.post_id}`}>{c.body_text.slice(0, 80)}</Link></td>
                  <td><Badge status={c.status} /></td><td>{c.moderation?.reason ?? "—"}</td><td>{fmtDate(c.created_at)}</td>
                </tr>))}
              </tbody>
            </table>
          ) : <p className="empty">Chưa có bình luận.</p>}
        </>
      )}
    </div>
  );
}
