import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import type { Notification } from "../lib/types";

const NAV = [
  ["/translate", "Dịch"], ["/dictionary", "Từ điển"], ["/conversation", "Hội thoại"],
  ["/community", "Cộng đồng"], ["/contribute", "Đóng góp"], ["/culture", "Văn hoá"],
] as const;

function Brand() {
  return (
    <Link to="/" className="brand" aria-label="Hriăm — trang chủ">
      <img src="/brand/mark.svg" width="36" height="36" alt="" />
      <span className="brand-text">
        <span className="brand-name small">Hriăm</span>
        <span className="brand-tag">Ê Đê · tiếng Kinh</span>
      </span>
    </Link>
  );
}

function UserMenu() {
  const { user, can, clear } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const notes = useQuery({
    queryKey: ["notifications"], enabled: !!user, refetchInterval: 60_000,
    queryFn: () => api.page<Notification[]>("/me/notifications"),
  });
  if (!user) {
    return (
      <div className="user-actions">
        <Link to="/login" className="btn ghost on-dark">Đăng nhập</Link>
        <Link to="/register" className="btn primary">Tham gia</Link>
      </div>
    );
  }
  const unread = Number(notes.data?.meta.unread ?? 0);
  const isStaff = ["moderation.review", "lexicon.review", "user.read", "audit.read", "dataset.read"].some(can);
  async function logout() {
    await api.post("/auth/logout").catch(() => undefined);
    clear();
    qc.clear();
    nav("/");
  }
  return (
    <div className="user-actions">
      <button className="user-btn" aria-expanded={open} aria-haspopup="menu" onClick={() => setOpen((o) => !o)}>
        <span className="avatar" aria-hidden>{user.display_name.slice(0, 1).toUpperCase()}</span>
        <span className="user-name">{user.display_name}</span>
        {unread > 0 && <span className="dot" aria-label={`${unread} thông báo mới`}>{unread}</span>}
      </button>
      {open && (
        <div className="menu" role="menu">
          <Link role="menuitem" to="/profile">Hồ sơ & thông báo{unread > 0 && ` (${unread})`}</Link>
          <Link role="menuitem" to="/community/my-submissions">Bài của tôi</Link>
          <Link role="menuitem" to="/contribute">Đóng góp của tôi</Link>
          <Link role="menuitem" to="/community/appeals">Khiếu nại</Link>
          {isStaff && <Link role="menuitem" to="/admin">Quản trị</Link>}
          <button role="menuitem" onClick={logout}>Đăng xuất</button>
        </div>
      )}
    </div>
  );
}

export function Layout() {
  const { user } = useAuth();
  const [menu, setMenu] = useState(false);
  const loc = useLocation();
  useEffect(() => { setMenu(false); window.scrollTo(0, 0); }, [loc.pathname]);
  return (
    <>
      <a href="#main" className="skip">Bỏ qua, tới nội dung chính</a>
      <header className="site-header">
        <div className="wrap nav-row">
          <Brand />
          <button className="nav-toggle" aria-expanded={menu} aria-controls="main-nav" onClick={() => setMenu((m) => !m)}>
            <span className="sr-only">Menu</span>☰
          </button>
          <nav id="main-nav" className={menu ? "open" : ""} aria-label="Chính">
            {NAV.map(([to, label]) => <NavLink key={to} to={to}>{label}</NavLink>)}
          </nav>
          <UserMenu />
        </div>
      </header>
      {user && user.status !== "active" && (
        <div className="banner bad" role="alert">
          Tài khoản đang bị khoá. Bạn vẫn xem được nội dung, strike và có thể <Link to="/community/appeals">gửi khiếu nại</Link>.
        </div>
      )}
      <main id="main"><Outlet /></main>
      <footer className="site-footer">
        <div className="hem" aria-hidden />
        <div className="wrap footer-row">
          <Brand />
          <nav className="foot-nav" aria-label="Chân trang">
            <Link to="/about">Về dự án</Link>
            <Link to="/rules">Quy tắc cộng đồng</Link>
            <Link to="/privacy">Quyền riêng tư</Link>
            <a href="/api/v1/docs">API</a>
          </nav>
        </div>
        <p className="wrap footer-note">Hriăm nghĩa là “học” trong tiếng Ê Đê. Bản dịch máy chỉ là bản nháp; dữ liệu chính thức cần người bản ngữ xác minh.</p>
      </footer>
    </>
  );
}
