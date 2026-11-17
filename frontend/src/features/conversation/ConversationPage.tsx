// Hội thoại theo lượt, chế độ dùng chung một thiết bị (docs/06 §2.1). Chưa có ASR tiếng Ê Đê nên mỗi lượt nhập bằng chữ
// (docs/09 §3: "nếu chưa hỗ trợ Ê Đê, cho phép nhập transcript"). Không lưu hội thoại: chỉ nằm trong bộ nhớ trình duyệt.
import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, ErrorBox, PageHead } from "../../components/ui";
import { api } from "../../lib/api";
import type { Lang, Translation } from "../../lib/types";

interface Turn { id: number; speaker: Lang; text: string; result?: Translation; error?: string }
const WHO: Record<Lang, string> = { ede: "Người nói tiếng Ê Đê", vi: "Người nói tiếng Kinh" };

export function ConversationPage() {
  const [speaker, setSpeaker] = useState<Lang>("vi");
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);
  const translate = useMutation({
    mutationFn: (t: Turn) => api.post<Translation>("/translations", { text: t.text, source_language: t.speaker, target_language: t.speaker === "ede" ? "vi" : "ede" }),
    onSuccess: (result, t) => setTurns((all) => all.map((x) => (x.id === t.id ? { ...x, result } : x))),
    onError: (e, t) => setTurns((all) => all.map((x) => (x.id === t.id ? { ...x, error: (e as Error).message } : x))),
  });
  function endTurn() {
    const t = text.trim();
    if (!t) return;
    const turn = { id: Date.now(), speaker, text: t };
    setTurns((all) => [...all, turn]);
    translate.mutate(turn);
    setText("");
    setSpeaker(speaker === "vi" ? "ede" : "vi"); // luân phiên lượt nói
  }
  return (
    <div className="wrap page">
      <PageHead eyebrow="Hội thoại" title="Hội thoại theo lượt">
        Hai người dùng chung một thiết bị, lần lượt nói. Chọn đúng người đang nói trước mỗi lượt. Hội thoại không được lưu lại.
      </PageHead>
      <div className="alert info">
        Nhận dạng giọng nói tiếng Ê Đê chưa có (cần bộ ghi âm có đồng ý của người nói và người bản ngữ đánh giá).
        Hiện mỗi lượt được nhập bằng chữ; nút nhấn giữ để nói sẽ bật khi có mô hình nhận dạng giọng nói đạt chất lượng.
      </div>
      <div className="convo">
        <ol className="turns" aria-live="polite">
          {turns.length === 0 && <li className="empty">Chưa có lượt nói nào.</li>}
          {turns.map((t) => (
            <li key={t.id} className={`turn ${t.speaker}`}>
              <p className="who">{WHO[t.speaker]}</p>
              <p className="said" lang={t.speaker === "ede" ? "rad" : "vi"}>{t.text}</p>
              {t.result ? (
                <p className="translated">{t.result.translated_text} <Badge status={t.result.translation_status} /></p>
              ) : t.error ? <p className="field-error">{t.error}</p> : <p className="muted"><span className="spin" /> Đang dịch…</p>}
            </li>
          ))}
        </ol>
        <div className="card form">
          <div className="seg" role="radiogroup" aria-label="Ai đang nói">
            {(["vi", "ede"] as Lang[]).map((l) => (
              <button key={l} role="radio" aria-checked={speaker === l} className={speaker === l ? "on" : ""} onClick={() => setSpeaker(l)}>{WHO[l]}</button>
            ))}
          </div>
          <p className="speaking" aria-live="polite">{WHO[speaker]} đang nói</p>
          <label className="sr-only" htmlFor="turn">Lời nói</label>
          <textarea id="turn" ref={ref} rows={3} value={text} onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); endTurn(); } }}
            placeholder={speaker === "ede" ? "Nhập câu tiếng Ê Đê…" : "Nhập câu tiếng Kinh…"} />
          {speaker === "ede" && <EdeKeyboard target={ref} onChange={setText} compact />}
          <ErrorBox error={translate.error} />
          <div className="row">
            <button className="btn primary" onClick={endTurn} disabled={!text.trim()}>Hoàn tất lượt nói</button>
            <button className="btn ghost" disabled title="Chưa có nhận dạng giọng nói tiếng Ê Đê">Nhấn giữ để nói</button>
            <span className="spacer" />
            {turns.length > 0 && <button className="btn ghost" onClick={() => setTurns([])}>Kết thúc & xoá</button>}
          </div>
        </div>
      </div>
      <p className="muted small">Chế độ hai thiết bị (phòng có mã tham gia) sẽ mở cùng nhận dạng giọng nói. <Link to="/privacy">Quyền riêng tư</Link></p>
    </div>
  );
}

export function RoomPage() {
  return (
    <div className="wrap page narrow">
      <PageHead eyebrow="Hội thoại" title="Phòng hội thoại hai thiết bị">
        Chế độ này cần nhận dạng giọng nói và kết nối thời gian thực, chưa được mở trong phiên bản hiện tại.
      </PageHead>
      <Link className="btn primary" to="/conversation">Dùng chế độ một thiết bị</Link>
    </div>
  );
}
