import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Badge, ErrorBox, PageHead, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Me, Notification } from "../../lib/types";

const ROLE: Record<string, string> = { user: "Thành viên", trusted_contributor: "Người đóng góp tin cậy", language_expert: "Chuyên gia ngôn ngữ", moderator: "Người kiểm duyệt", admin: "Quản trị viên" };
const EVENT: Record<string, string> = { strike_applied: "Nhận strike", strike_revoked: "Huỷ strike (khiếu nại được chấp nhận)", strike_reinstated: "Khôi phục strike", admin_adjustment: "Điều chỉnh" };

export function ProfilePage() {
  const { user, setUser } = useAuth();
  const qc = useQueryClient();
  const notes = useQuery({ queryKey: ["notifications"], queryFn: () => api.page<Notification[]>("/me/notifications") });
  const strikes = useQuery({ queryKey: ["my-strikes"], queryFn: () => api.get<{ effective_strikes: number; ban_threshold: number; events: { id: string; event_type: string; quantity: number; reason_code: string; created_at: string }[] }>("/me/strikes") });
  const history = useQuery({ queryKey: ["history"], queryFn: () => api.get<{ id: string; source_text: string; translated_text: string; translation_status: string; created_at: string }[]>("/translations/history") });
  const markRead = useMutation({ mutationFn: () => api.post("/me/notifications/read"), onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }) });
  const toggle = useMutation({ mutationFn: (v: boolean) => api.patch<Me>("/me", { save_translation_history: v }), onSuccess: setUser });
  const clear = useMutation({ mutationFn: () => api.del("/translations/history"), onSuccess: () => qc.invalidateQueries({ queryKey: ["history"] }) });
  const unread = Number(notes.data?.meta.unread ?? 0);
  useEffect(() => { if (unread) { const t = setTimeout(() => markRead.mutate(), 3000); return () => clearTimeout(t); } }, [unread]); // eslint-disable-line
  if (!user) return null;
  return (
    <div className="wrap page">
      <PageHead eyebrow="Hồ sơ" title={user.display_name}>
        @{user.username} · <Badge status={user.status} /> · {user.roles.map((r) => ROLE[r] ?? r).join(", ")}
      </PageHead>
      <div className="two-col">
        <section>
          <h2>Thông báo</h2>
          {notes.data?.data.length ? (
            <ul className="list">
              {notes.data.data.map((n) => (
                <li key={n.id} className={`list-item${n.read ? "" : " unread"}`}>
                  <b>{n.title}</b>{n.body && <p className="muted">{n.body}</p>}
                  <p className="muted small">{fmtDate(n.created_at)} {n.link && <Link to={n.link}>Xem</Link>}</p>
                </li>
              ))}
            </ul>
          ) : <p className="empty">Chưa có thông báo.</p>}
        </section>
        <section>
          <h2>Strike</h2>
          <p>Strike hiệu lực: <b>{strikes.data?.effective_strikes ?? 0}</b> (tài khoản bị khoá khi vượt quá {strikes.data?.ban_threshold ?? 3}).{" "}
            <Link to="/community/appeals">Khiếu nại</Link></p>
          {strikes.data?.events.length ? (
            <ul className="list">{strikes.data.events.map((e) => (
              <li key={e.id} className="list-item">{EVENT[e.event_type] ?? e.event_type} ({e.quantity > 0 ? "+" : ""}{e.quantity}) · {e.reason_code} · {fmtDate(e.created_at)}</li>
            ))}</ul>
          ) : null}
          <h2 className="mt">Lịch sử dịch</h2>
          <label className="check">
            <input type="checkbox" checked={user.save_translation_history} onChange={(e) => toggle.mutate(e.target.checked)} />
            Lưu lịch sử dịch của tôi (mặc định tắt)
          </label>
          <ErrorBox error={toggle.error} />
          {history.data?.length ? (
            <>
              <ul className="list">{history.data.slice(0, 20).map((h) => (
                <li key={h.id} className="list-item"><b>{h.source_text}</b><p>{h.translated_text} <Badge status={h.translation_status} /></p><p className="muted small">{fmtDate(h.created_at)}</p></li>
              ))}</ul>
              <button className="btn ghost danger" onClick={() => clear.mutate()}>Xoá toàn bộ lịch sử</button>
            </>
          ) : <p className="empty">Không có lịch sử.</p>}
        </section>
      </div>
    </div>
  );
}
