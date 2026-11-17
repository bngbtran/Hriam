import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface Release { id: string; version: string; status: string; checksum_sha256: string; record_counts: Record<string, number>;
  license_inventory: { name: string; review_status: string; sources: string[] }[]; change_summary: string; manifest_uri: string; released_at: string; created_by: string | null }
interface Src { code: string; name: string; source_type: string; reference: string; notes: string; license: { name: string; review_status: string; commercial_allowed: boolean | null; notes: string } | null }

export function AdminReleases() {
  const qc = useQueryClient();
  const { can } = useAuth();
  const list = useQuery({ queryKey: ["releases"], queryFn: () => api.get<Release[]>("/admin/dataset-releases") });
  const sources = useQuery({ queryKey: ["sources"], queryFn: () => api.get<Src[]>("/admin/sources") });
  const now = new Date();
  const [version, setVersion] = useState(`${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, "0")}`);
  const [summary, setSummary] = useState("");
  const create = useMutation({ mutationFn: () => api.post("/admin/dataset-releases", { version, change_summary: summary }, true),
    onSuccess: () => { setSummary(""); qc.invalidateQueries({ queryKey: ["releases"] }); } });
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Dataset releases">
        Mỗi release là snapshot bất biến có manifest, checksum và kiểm kê giấy phép. Release có nguồn chưa duyệt giấy phép chỉ dùng cho nghiên cứu.
        Duyệt đóng góp không tự huấn luyện lại mô hình.
      </PageHead>
      {can("dataset.release") && (
        <form className="card form inline-form" onSubmit={(e) => { e.preventDefault(); create.mutate(); }}>
          <label>Phiên bản<input value={version} onChange={(e) => setVersion(e.target.value)} placeholder="2026.11" /></label>
          <label>Tóm tắt thay đổi<input value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <ErrorBox error={create.error} />
          <button className="btn primary" disabled={summary.length < 3 || create.isPending}>Tạo release</button>
        </form>
      )}
      {list.isLoading ? <Spinner /> : !list.data?.length ? <Empty>Chưa có release.</Empty> : (
        <table className="table mt">
          <thead><tr><th>Phiên bản</th><th>Trạng thái</th><th>Bản ghi</th><th>Checksum</th><th>Ngày</th></tr></thead>
          <tbody>{list.data.map((r) => (
            <tr key={r.id}>
              <td><b>{r.version}</b><div className="muted small">{r.change_summary}</div></td>
              <td><Badge status={r.status} /></td>
              <td>{Object.entries(r.record_counts).map(([k, v]) => `${v} ${k === "lexical_entry" ? "mục từ" : "cặp câu"}`).join(", ")}</td>
              <td><code title={r.checksum_sha256}>{r.checksum_sha256.slice(0, 12)}…</code></td>
              <td>{fmtDate(r.released_at)}<div className="muted small">{r.created_by}</div></td>
            </tr>))}
          </tbody>
        </table>
      )}
      <h2 className="mt">Nguồn và giấy phép</h2>
      <ul className="list">{sources.data?.map((s) => (
        <li key={s.code} className="list-item">
          <div className="row-between"><b>{s.name}</b>{s.license && <Badge status={s.license.review_status === "approved" ? "approved" : "pending"} />}</div>
          <p className="muted small">{s.license?.name} · {s.reference}</p>
          {(s.notes || s.license?.notes) && <p className="small">{s.notes} {s.license?.notes}</p>}
        </li>))}
      </ul>
    </>
  );
}
