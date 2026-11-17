import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../../lib/auth";

// Hiển thị theo quyền chỉ để tiện; backend vẫn kiểm tra quyền ở mọi endpoint.
export const ADMIN_SECTIONS = [
  ["moderation", "Kiểm duyệt", "moderation.review", "Hàng chờ người duyệt, báo cáo, quyết định và strike"],
  ["contributions", "Đóng góp", "lexicon.review", "Duyệt từ, nghĩa, cụm, cặp câu vào Master Lexicon"],
  ["lexical-candidates", "Ứng viên AI", "lexicon.candidate_review", "Từ/nghĩa/cụm do hệ thống phát hiện"],
  ["appeals", "Khiếu nại", "appeal.review", "Xem xét khiếu nại, đảo strike"],
  ["users", "Người dùng", "user.read", "Vai trò, khoá/mở khoá, hạn chế số điện thoại"],
  ["dataset-releases", "Dataset", "dataset.read", "Phát hành dữ liệu, nguồn, giấy phép"],
  ["audit", "Nhật ký", "audit.read", "Nhật ký kiểm toán thao tác quản trị"],
  ["settings", "Cấu hình", "settings.manage", "Chuẩn chữ viết, chính sách kiểm duyệt, mô hình"],
] as const;

export function AdminLayout() {
  const { can } = useAuth();
  const sections = ADMIN_SECTIONS.filter(([, , perm]) => can(perm));
  if (!sections.length) return <div className="wrap page"><p className="alert error">Bạn không có quyền quản trị.</p></div>;
  return (
    <div className="wrap page admin">
      <nav className="admin-nav" aria-label="Quản trị">
        <NavLink end to="/admin">Tổng quan</NavLink>
        {sections.map(([to, label]) => <NavLink key={to} to={`/admin/${to}`}>{label}</NavLink>)}
      </nav>
      <div className="admin-body"><Outlet /></div>
    </div>
  );
}
