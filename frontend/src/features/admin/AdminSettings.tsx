import { useQuery } from "@tanstack/react-query";
import { Badge, ErrorBox, PageHead, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

interface Settings {
  moderation_policy_version: string; moderation_terms: { term: string; category: string }[];
  orthography_profiles: { code: string; name: string; version: string; status: string; characters: number }[];
  licenses: { name: string; review_status: string }[];
  translation_adapters: Record<string, { available: boolean; model_version: string | null; license: string; sends_data_externally: boolean; limits: string }>;
  roles: Record<string, string[]>;
}

export function AdminSettings() {
  const q = useQuery({ queryKey: ["admin-settings"], queryFn: () => api.get<Settings>("/admin/settings") });
  if (q.isLoading) return <Spinner />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const s = q.data;
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Cấu hình">Chỉ xem. Thay đổi chuẩn chữ viết, danh sách từ cần xem và giấy phép thực hiện qua quy trình có phê duyệt và tăng phiên bản.</PageHead>
      <h2>Mô hình dịch</h2>
      <table className="table"><thead><tr><th>Chiều</th><th>Trạng thái</th><th>Phiên bản</th><th>Giấy phép</th><th>Gửi dữ liệu ra ngoài</th></tr></thead>
        <tbody>{Object.entries(s.translation_adapters).map(([d, a]) => (
          <tr key={d}><td>{d === "ede2vi" ? "Ê Đê → Kinh" : "Kinh → Ê Đê"}</td><td><Badge status={a.available ? "active" : "pending"} /></td>
            <td>{a.model_version ?? "—"}</td><td>{a.license}</td><td>{a.sends_data_externally ? "Có" : "Không"}</td></tr>))}
        </tbody></table>
      <h2 className="mt">Chuẩn chữ viết</h2>
      <ul className="list">{s.orthography_profiles.map((p) => (
        <li key={p.code} className="list-item row-between"><span><b>{p.name}</b> v{p.version} · {p.characters} ký tự đặc thù</span><Badge status={p.status === "approved" ? "approved" : "draft"} /></li>))}
      </ul>
      <h2 className="mt">Kiểm duyệt</h2>
      <p>Chính sách <code>{s.moderation_policy_version}</code>. Cụm cần người xem lại (không phải kết luận vi phạm):</p>
      <p>{s.moderation_terms.map((t) => <span key={t.term} className="tag">{t.term}</span>)}</p>
      <h2 className="mt">Vai trò và quyền</h2>
      <table className="table"><tbody>{Object.entries(s.roles).map(([r, perms]) => (
        <tr key={r}><td><b>{r}</b></td><td className="small">{perms.join(", ")}</td></tr>))}</tbody></table>
    </>
  );
}
