import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { PageHead } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { ADMIN_SECTIONS } from "./AdminLayout";

export function AdminHome() {
  const { can } = useAuth();
  const mod = useQuery({ queryKey: ["admin-counts"], enabled: can("moderation.review"),
    queryFn: () => api.page<unknown[]>("/admin/moderation/cases", { limit: 1 }) });
  const contrib = useQuery({ queryKey: ["admin-contrib-count"], enabled: can("lexicon.review"),
    queryFn: () => api.page<unknown[]>("/admin/contributions", { limit: 100 }) });
  const counts = mod.data?.meta.counts as Record<string, number> | undefined;
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Tổng quan" />
      <div className="stat-row">
        {counts && <Link to="/admin/moderation" className="stat"><b>{counts.human_review}</b><span>chờ người duyệt</span></Link>}
        {counts && <Link to="/admin/moderation?queue=reports" className="stat"><b>{counts.reports}</b><span>báo cáo mở</span></Link>}
        {contrib.data && <Link to="/admin/contributions" className="stat"><b>{contrib.data.data.length}{contrib.data.meta.next_cursor ? "+" : ""}</b><span>đóng góp chờ duyệt</span></Link>}
      </div>
      <div className="cards grid mt">
        {ADMIN_SECTIONS.filter(([, , p]) => can(p)).map(([to, label, , desc]) => (
          <Link key={to} to={`/admin/${to}`} className="card link-card"><h3>{label}</h3><p className="muted">{desc}</p></Link>
        ))}
      </div>
    </>
  );
}
