import { useInfiniteQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ErrorBox, LoadMore, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";

interface Log { id: string; actor: string | null; action: string; target_type: string; target_id: string; reason_code: string | null; metadata: Record<string, unknown>; created_at: string }

export function AdminAudit() {
  const [action, setAction] = useState("");
  const q = useInfiniteQuery({
    queryKey: ["audit", action],
    queryFn: ({ pageParam }) => api.page<Log[]>("/admin/audit", { action, cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.meta.next_cursor ?? undefined,
  });
  const rows = q.data?.pages.flatMap((p) => p.data) ?? [];
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Nhật ký kiểm toán">Không chứa token, số điện thoại, nội dung bị từ chối hay âm thanh.</PageHead>
      <div className="chips">
        {[["", "Tất cả"], ["moderation", "Kiểm duyệt"], ["strike", "Strike"], ["appeal", "Khiếu nại"], ["contribution", "Đóng góp"], ["user", "Người dùng"], ["dataset", "Dataset"]].map(([v, l]) => (
          <button key={v} className={action === v ? "on" : ""} onClick={() => setAction(v)}>{l}</button>
        ))}
      </div>
      <ErrorBox error={q.error} />
      {q.isLoading ? <Spinner /> : (
        <table className="table">
          <thead><tr><th>Thời gian</th><th>Người thực hiện</th><th>Thao tác</th><th>Đối tượng</th><th>Lý do</th></tr></thead>
          <tbody>{rows.map((a) => (
            <tr key={a.id}><td>{fmtDate(a.created_at)}</td><td>{a.actor ?? "hệ thống"}</td><td><code>{a.action}</code></td>
              <td>{a.target_type} <span className="muted small">{a.target_id.slice(0, 8)}</span></td><td>{a.reason_code ?? "—"}</td></tr>
          ))}</tbody>
        </table>
      )}
      <LoadMore hasMore={!!q.hasNextPage} onClick={() => q.fetchNextPage()} />
    </>
  );
}
