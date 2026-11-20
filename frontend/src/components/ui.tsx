import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { errorText } from "../lib/api";
import { useAuth } from "../lib/auth";

export const fmtDate = (s?: string | null) =>
  s ? new Date(s).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "—";

export function Spinner({ label = "Đang tải…" }: { label?: string }) {
  return <p className="muted" role="status"><span className="spin" aria-hidden /> {label}</p>;
}

export function ErrorBox({ error }: { error: unknown }) {
  return error ? <p className="alert error" role="alert">{errorText(error)}</p> : null;
}

export function Empty({ children, motif = "qua-tram" }: { children: ReactNode; motif?: string }) {
  return (
    <div className="empty-state">
      <img src={`/brand/icon-${motif}.svg`} width="40" height="40" alt="" />
      <div>{children}</div>
    </div>
  );
}

const STATUS: Record<string, [string, string]> = {
  // Trạng thái bản dịch (docs/07 §3)
  verified_memory: ["Đã xác minh", "ok"], expert_verified: ["Chuyên gia xác minh", "ok"],
  dictionary_example: ["Ví dụ trong từ điển", "info"],
  machine_draft: ["Bản nháp máy dịch", "warn"], needs_review: ["Cần xem lại", "warn"],
  // Nghĩa trong từ điển
  verified: ["Đã xác minh", "ok"], draft: ["Chưa xác minh", "muted"], deprecated: ["Ngừng dùng", "muted"],
  // Nội dung cộng đồng
  pending_moderation: ["Đang kiểm tra", "warn"], pending_human_review: ["Chờ người duyệt", "warn"],
  published: ["Đã đăng", "ok"], rejected: ["Bị từ chối", "bad"], removed: ["Đã gỡ", "bad"],
  // Đóng góp, khiếu nại
  pending: ["Chờ duyệt", "warn"], in_review: ["Đang duyệt", "warn"], approved: ["Đã duyệt", "ok"],
  withdrawn: ["Đã rút", "muted"], purged: ["Đã xoá", "muted"], accepted: ["Chấp nhận", "ok"],
  // Tài khoản
  active: ["Hoạt động", "ok"], permanently_banned: ["Bị khoá", "bad"], suspended: ["Tạm khoá", "bad"],
  released: ["Đã phát hành", "ok"], research_only: ["Chỉ nghiên cứu", "warn"],
};

export function Badge({ status }: { status: string }) {
  const [label, tone] = STATUS[status] ?? [status, "muted"];
  return <span className={`badge ${tone}`}>{label}</span>;
}

export function PageHead({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
  return (
    <header className="page-head">
      {eyebrow && <p className="eyebrow dark"><span className="pip" />{eyebrow}</p>}
      <h1 className="page-title">{title}</h1>
      {children && <div className="hint">{children}</div>}
    </header>
  );
}

export function RequireAuth({ children, perm }: { children: ReactNode; perm?: string }) {
  const { user, ready, can } = useAuth();
  const loc = useLocation();
  if (!ready) return <Spinner />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (perm && !can(perm)) return <p className="alert error">Bạn không có quyền truy cập trang này.</p>;
  return <>{children}</>;
}

export function LoginPrompt({ action }: { action: string }) {
  const loc = useLocation();
  return (
    <p className="alert info">
      <Link to={`/login?next=${encodeURIComponent(loc.pathname)}`}>Đăng nhập</Link> hoặc{" "}
      <Link to="/register">tạo tài khoản</Link> để {action}.
    </p>
  );
}

export function LoadMore({ hasMore, onClick, loading }: { hasMore: boolean; onClick: () => void; loading?: boolean }) {
  return hasMore ? (
    <div className="load-more">
      <button className="btn ghost" onClick={onClick} disabled={loading}>{loading ? "Đang tải…" : "Xem thêm"}</button>
    </div>
  ) : null;
}
