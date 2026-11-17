import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { Empty, ErrorBox, LoadMore, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Post } from "../../lib/types";

export function useCategories() {
  return useQuery({ queryKey: ["categories"], staleTime: Infinity,
    queryFn: () => api.get<{ code: string; label: string }[]>("/forum/categories") });
}

export function FeedPage() {
  const [params, setParams] = useSearchParams();
  const category = params.get("category") ?? "";
  const { user } = useAuth();
  const cats = useCategories();
  const feed = useInfiniteQuery({
    queryKey: ["feed", category],
    queryFn: ({ pageParam }) => api.page<Post[]>("/forum/posts", { category, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.meta.next_cursor ?? undefined,
  });
  const posts = feed.data?.pages.flatMap((p) => p.data) ?? [];
  return (
    <div className="wrap page">
      <PageHead eyebrow="Cộng đồng" title="Hỏi đáp, chia sẻ và góp ý">
        Mọi bài viết được kiểm duyệt trước khi hiển thị. Bài có tiếng Ê Đê được người duyệt xem trực tiếp, không bị máy tự đánh giá.{" "}
        <Link to="/rules">Quy tắc cộng đồng</Link>
      </PageHead>
      <div className="toolbar">
        <div className="chips" role="tablist" aria-label="Danh mục">
          <button role="tab" aria-selected={!category} className={!category ? "on" : ""} onClick={() => setParams({})}>Tất cả</button>
          {cats.data?.map((c) => (
            <button key={c.code} role="tab" aria-selected={category === c.code} className={category === c.code ? "on" : ""}
              onClick={() => setParams({ category: c.code })}>{c.label}</button>
          ))}
        </div>
        <span className="spacer" />
        {user ? <Link className="btn primary" to="/community/new">Viết bài</Link> : <Link className="btn ghost" to="/login?next=/community/new">Đăng nhập để viết bài</Link>}
      </div>
      <ErrorBox error={feed.error} />
      {feed.isLoading ? <Spinner /> : posts.length === 0 ? <Empty motif="chuon-chuon">Chưa có bài viết nào trong mục này.</Empty> : (
        <ul className="post-list">
          {posts.map((p) => (
            <li key={p.id}>
              <Link to={`/community/posts/${p.id}`} className="post-row">
                <span className="tag">{p.category_label}</span>
                <h3>{p.title}</h3>
                <p className="excerpt">{p.body_text.slice(0, 180)}{p.body_text.length > 180 && "…"}</p>
                <p className="muted small">{p.author} · {fmtDate(p.published_at)} · {p.comment_count ?? 0} bình luận</p>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <div className="center"><LoadMore hasMore={!!feed.hasNextPage} loading={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()} /></div>
    </div>
  );
}
