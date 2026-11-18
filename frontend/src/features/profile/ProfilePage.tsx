import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, ErrorBox, PageHead, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Me, Notification } from "../../lib/types";

const ROLE: Record<string, string> = { user: "Thành viên", trusted_contributor: "Người đóng góp tin cậy", language_expert: "Chuyên gia ngôn ngữ", moderator: "Người kiểm duyệt", admin: "Quản trị viên" };
const EVENT: Record<string, string> = { strike_applied: "Nhận strike", strike_revoked: "Huỷ strike (khiếu nại được chấp nhận)", strike_reinstated: "Khôi phục strike", admin_adjustment: "Điều chỉnh" };

function PhoneVerificationSection({ user, onUpdated }: { user: Me; onUpdated: (u: Me) => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [step, setStep] = useState<"idle" | "code_sent">("idle");
  const [hint, setHint] = useState<string | null>(null);
  const [masked, setMasked] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const requestCode = useMutation({
    mutationFn: () => api.post<{ status: string; phone_masked: string; dev_code_hint?: string }>("/auth/request-phone-code", { phone }),
    onSuccess: (data) => {
      setStep("code_sent");
      setMasked(data.phone_masked);
      if (data.dev_code_hint) setHint(data.dev_code_hint);
      setErrorMsg(null);
      setSuccessMsg(`Mã xác thực đã được gửi tới ${data.phone_masked}.`);
    },
    onError: (e) => {
      setErrorMsg((e as Error).message);
      setSuccessMsg(null);
    },
  });

  const verifyCode = useMutation({
    mutationFn: () => api.post<{ verified: boolean; phone_masked: string }>("/auth/verify-phone", { code }),
    onSuccess: async () => {
      setSuccessMsg("Xác thực số điện thoại thành công!");
      setErrorMsg(null);
      setStep("idle");
      setCode("");
      const me = await api.get<Me>("/me");
      onUpdated(me);
    },
    onError: (e) => {
      setErrorMsg((e as Error).message);
    },
  });

  return (
    <div className="card mt">
      <h3>Xác minh số điện thoại (Chống lạm dụng & Bảo vệ cộng đồng)</h3>
      <p className="muted small">
        Hệ thống không lưu số điện thoại ở dạng văn bản rõ; chỉ lưu mã băm HMAC có muối để chống tài khoản ảo và spam (docs/08 §3).
      </p>
      {user.phone_verified ? (
        <div className="alert success">
          ✓ Số điện thoại của bạn đã được xác minh bảo mật.
        </div>
      ) : (
        <div>
          {user.has_phone && !user.phone_verified && (
            <div className="alert warning">
              Bạn đã đăng ký số điện thoại nhưng chưa hoàn tất xác thực OTP.
            </div>
          )}
          {step === "idle" ? (
            <form onSubmit={(e) => { e.preventDefault(); if (phone.trim()) requestCode.mutate(); }} className="form">
              <label htmlFor="phone_input">Số điện thoại (Việt Nam)</label>
              <div className="row">
                <input
                  id="phone_input"
                  type="tel"
                  placeholder="Ví dụ: 0912345678 hoặc +84912345678"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                />
                <button type="submit" className="btn primary" disabled={requestCode.isPending || !phone.trim()}>
                  {requestCode.isPending ? "Đang gửi..." : "Gửi mã xác thực (SMS)"}
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); if (code.trim()) verifyCode.mutate(); }} className="form">
              <p className="small">Mã xác thực 6 chữ số gửi tới <b>{masked}</b> (hết hạn sau 10 phút):</p>
              {hint && (
                <div className="alert info">
                  Mã OTP thử nghiệm (Dev hint): <b>{hint}</b>
                </div>
              )}
              <div className="row">
                <input
                  id="code_input"
                  type="text"
                  maxLength={6}
                  placeholder="Nhập 6 chữ số"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  required
                />
                <button type="submit" className="btn primary" disabled={verifyCode.isPending || code.length < 6}>
                  {verifyCode.isPending ? "Đang xác minh..." : "Xác nhận mã"}
                </button>
                <button type="button" className="btn ghost" onClick={() => { setStep("idle"); setErrorMsg(null); }}>
                  Đổi số khác
                </button>
              </div>
            </form>
          )}
          {errorMsg && <p className="field-error">{errorMsg}</p>}
          {successMsg && <p className="alert success">{successMsg}</p>}
        </div>
      )}
    </div>
  );
}

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
          <h2 id="thong-bao" className="anchor">Thông báo</h2>
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
          <PhoneVerificationSection user={user} onUpdated={setUser} />
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
