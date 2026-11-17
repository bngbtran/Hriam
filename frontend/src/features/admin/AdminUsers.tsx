import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";

interface Row { id: string; username: string; display_name: string; status: string; roles: string[]; created_at: string; effective_strikes: number }
interface Detail extends Row { has_phone: boolean; posts: number; comments: number; available_roles: string[] }
const ROLE: Record<string, string> = { user: "Thành viên", trusted_contributor: "Đóng góp tin cậy", language_expert: "Chuyên gia ngôn ngữ", moderator: "Kiểm duyệt", admin: "Quản trị" };

export function AdminUsers() {
  const [q, setQ] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const { can } = useAuth();
  const list = useQuery({ queryKey: ["admin-users", q], queryFn: () => api.get<Row[]>("/admin/users", { q }) });
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Người dùng" />
      <div className="search small-search"><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Tìm theo tên…" aria-label="Tìm người dùng" /></div>
      <ErrorBox error={list.error} />
      <div className="master-detail">
        <div>
          {list.isLoading ? <Spinner /> : !list.data?.length ? <Empty>Không có người dùng.</Empty> : (
            <ul className="list selectable">{list.data.map((u) => (
              <li key={u.id}><button className={`list-item${selected === u.id ? " on" : ""}`} onClick={() => setSelected(u.id)}>
                <span className="row-between"><b>{u.display_name} <span className="muted">@{u.username}</span></b><Badge status={u.status} /></span>
                <span className="muted small">{u.roles.map((r) => ROLE[r] ?? r).join(", ")} · {u.effective_strikes} strike · {fmtDate(u.created_at)}</span>
              </button></li>))}
            </ul>
          )}
        </div>
        <div>
          {selected ? <UserDetail id={selected} /> : <p className="muted">Chọn người dùng.</p>}
          {can("phone_restriction.manage") && <PhoneRestrictions />}
        </div>
      </div>
    </>
  );
}

function UserDetail({ id }: { id: string }) {
  const qc = useQueryClient();
  const { can, user: me } = useAuth();
  const q = useQuery({ queryKey: ["admin-user", id], queryFn: () => api.get<Detail>(`/admin/users/${id}`) });
  const audit = useQuery({ queryKey: ["admin-user-audit", id], enabled: can("audit.read"),
    queryFn: () => api.get<{ action: string; reason_code: string | null; created_at: string }[]>(`/admin/users/${id}/audit`) });
  const [roles, setRoles] = useState<string[] | null>(null);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const refresh = () => { qc.invalidateQueries({ queryKey: ["admin-user", id] }); qc.invalidateQueries({ queryKey: ["admin-users"] }); qc.invalidateQueries({ queryKey: ["admin-user-audit", id] }); };
  const saveRoles = useMutation({ mutationFn: () => api.put(`/admin/users/${id}/roles`, { roles, note: note || "Cập nhật vai trò" }), onSuccess: () => { setRoles(null); refresh(); } });
  const ban = useMutation({ mutationFn: (b: boolean) => api.post(`/admin/users/${id}/${b ? "ban" : "unban"}`, { reason_code: reason, note }, true), onSuccess: refresh });
  if (q.isLoading) return <Spinner />;
  if (!q.data) return <ErrorBox error={q.error} />;
  const u = q.data;
  const current = roles ?? u.roles;
  return (
    <div className="card detail">
      <p className="row-between"><b>{u.display_name} @{u.username}</b><Badge status={u.status} /></p>
      <p className="muted small">{u.posts} bài · {u.comments} bình luận · {u.effective_strikes} strike · {u.has_phone ? "có số điện thoại (đã băm)" : "không có số điện thoại"}</p>
      {can("user.roles") && (
        <fieldset className="consents">
          <legend>Vai trò</legend>
          {u.available_roles.map((r) => (
            <label key={r} className="check"><input type="checkbox" disabled={r === "user"} checked={current.includes(r)}
              onChange={(e) => setRoles(e.target.checked ? [...current, r] : current.filter((x) => x !== r))} /> {ROLE[r] ?? r}</label>
          ))}
          {roles && <button className="btn primary" onClick={() => saveRoles.mutate()} disabled={saveRoles.isPending}>Lưu vai trò</button>}
        </fieldset>
      )}
      {(can("user.ban") || can("user.unban")) && u.id !== me?.id && (
        <div className="form">
          <label>Mã lý do<input value={reason} onChange={(e) => setReason(e.target.value.toUpperCase())} placeholder="VD: SEVERE_ABUSE, APPEAL_REVIEW" /></label>
          <label>Ghi chú (bắt buộc)<input value={note} onChange={(e) => setNote(e.target.value)} /></label>
          <div className="row">
            {u.status === "active" && can("user.ban") && <button className="btn danger" disabled={reason.length < 2 || note.length < 3} onClick={() => confirm("Khoá tài khoản này?") && ban.mutate(true)}>Khoá tài khoản</button>}
            {u.status !== "active" && can("user.unban") && <button className="btn primary" disabled={reason.length < 2 || note.length < 3} onClick={() => ban.mutate(false)}>Mở khoá</button>}
          </div>
        </div>
      )}
      <ErrorBox error={saveRoles.error ?? ban.error} />
      {audit.data && audit.data.length > 0 && (
        <><h4>Nhật ký</h4><ul className="timeline">{audit.data.map((a, i) => <li key={i}>{fmtDate(a.created_at)} · {a.action}{a.reason_code && ` (${a.reason_code})`}</li>)}</ul></>
      )}
    </div>
  );
}

function PhoneRestrictions() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["phone-restrictions"], queryFn: () => api.get<{ id: string; status: string; reason_code: string; created_at: string; restriction_type: string }[]>("/admin/phone-restrictions") });
  const release = useMutation({
    mutationFn: ({ id, note }: { id: string; note: string }) => api.post(`/admin/phone-restrictions/${id}/release`, { reason_code: "NUMBER_REASSIGNED", note }, true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["phone-restrictions"] }),
  });
  if (!q.data?.length) return null;
  return (
    <section className="mt">
      <h3>Hạn chế số điện thoại</h3>
      <p className="muted small">Chỉ lưu mã HMAC; không hiển thị số. Gỡ khi số được nhà mạng cấp lại cho người khác.</p>
      <ul className="list">{q.data.map((r) => (
        <li key={r.id} className="list-item row-between">
          <span>{r.reason_code} · {fmtDate(r.created_at)} <Badge status={r.status === "active" ? "pending" : "released"} /></span>
          {r.status === "active" && <button className="link" onClick={() => { const note = prompt("Lý do gỡ hạn chế?"); if (note && note.length >= 3) release.mutate({ id: r.id, note }); }}>Gỡ</button>}
        </li>))}
      </ul>
    </section>
  );
}
