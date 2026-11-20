// Dịch văn bản (docs/01 §4.2, §5.1): tra dữ liệu đã xác minh trước, rồi mới dùng mô hình; hiển thị trạng thái và độ không chắc chắn.
import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, ErrorBox } from "../../components/ui";
import { api, errorText } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Lang, Translation } from "../../lib/types";

const NAMES: Record<Lang, string> = { ede: "Ê Đê", vi: "Tiếng Kinh" };
const SAMPLES: Record<Lang, string[]> = {
  vi: ["Tôi muốn ăn cơm", "Nhà anh ở đâu?", "Hôm nay trời mưa to", "Cảm ơn nhiều"],
  ede: ["Adŭ hriăm", "Kâo čiăng ƀơ̆ng êsei", "Ti sang ih?"],
};

type Engine = "local" | "gemini";
interface Engines { default: string; local: { available: Record<string, boolean> }; gemini: { available: boolean; model: string | null } }
const ENGINE_KEY = "hriam.engine";

export function TranslatePage() {
  const [params, setParams] = useSearchParams();
  const [source, setSource] = useState<Lang>(params.get("from") === "ede" ? "ede" : "vi");
  const [text, setText] = useState(params.get("text") ?? "");
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState(false);
  const input = useRef<HTMLTextAreaElement>(null);
  const target: Lang = source === "ede" ? "vi" : "ede";
  const caps = useQuery({ queryKey: ["mt-caps"], queryFn: () => api.get<Record<string, { available: boolean; model_version: string | null }>>("/translations/capabilities") });
  const engines = useQuery({ queryKey: ["mt-engines"], queryFn: () => api.get<Engines>("/translations/engines") });
  const [chosen, setChosen] = useState<Engine | null>(() => {
    try { const v = localStorage.getItem(ENGINE_KEY); return v === "local" || v === "gemini" ? v : null; } catch { return null; }
  });
  const geminiOk = !!engines.data?.gemini.available;
  // Chưa chọn thì theo cấu hình máy chủ; Gemini không dùng được thì luôn là mô hình Hriăm.
  const engine: Engine = geminiOk && (chosen ?? (engines.data?.default === "gemini" ? "gemini" : "local")) === "gemini" ? "gemini" : "local";
  const run = useMutation({
    mutationFn: ({ t, e }: { t: string; e: Engine }) =>
      api.post<Translation>("/translations", { text: t, source_language: source, target_language: target, engine: e }),
  });

  useEffect(() => { if (params.get("text")) run.mutate({ t: params.get("text")!, e: engine }); /* eslint-disable-next-line */ }, [engines.isSuccess]);

  function pick(e: Engine) {
    setChosen(e);
    try { localStorage.setItem(ENGINE_KEY, e); } catch { /* chế độ riêng tư: bỏ qua */ }
    if (run.data && text.trim()) run.mutate({ t: text.trim(), e });  // đổi bộ dịch thì dịch lại ngay
  }

  function submit() {
    const t = text.trim();
    if (!t) return;
    setFeedback(false);
    setParams({ from: source, text: t }, { replace: true });
    run.mutate({ t, e: engine });
  }
  function swap() {
    setSource(target);
    if (run.data?.translated_text && run.data.translation_status !== "needs_review") setText(run.data.translated_text);
    run.reset();
  }
  const result = run.data;
  const mtOn = caps.data?.[`${source}2${target}`]?.available;

  return (
    <div className="studio">
      <div className="wrap">
        <p className="eyebrow dark"><span className="pip" />Dịch hai chiều</p>
        <h1 className="h-hero">Ê Đê ↔ tiếng Kinh</h1>
        <p className="lead">
          Hệ thống tra từ điển và câu đã được xác minh trước; nếu chưa có mới dùng mô hình dịch máy
          {caps.data && !mtOn && " (chiều này chưa có mô hình, chỉ ghép nghĩa theo từ điển)"}.
        </p>
        <div className="engine-switch" role="group" aria-label="Bộ dịch máy">
          <span className="engine-label">Dịch máy bằng</span>
          <button type="button" aria-pressed={engine === "local"} className={engine === "local" ? "on" : ""}
            onClick={() => pick("local")}>Mô hình Hriăm</button>
          <button type="button" aria-pressed={engine === "gemini"} className={engine === "gemini" ? "on" : ""}
            disabled={!geminiOk} title={geminiOk ? undefined : "Máy chủ chưa cấu hình GEMINI_API_KEY"}
            onClick={() => pick("gemini")}>Gemini</button>
          <span className="engine-note">
            {engine === "gemini" ? "Văn bản được gửi tới Google để dịch. Chậm hơn nhưng thường chính xác hơn."
              : "Chạy trên máy chủ dự án, không gửi dữ liệu ra ngoài. Nhanh nhưng còn yếu với câu đời thường."}
          </span>
        </div>
        <section className="translator" aria-label="Khung dịch">
          <div className="lang-bar">
            <div className="lang-tab"><span className={`lang-dot ${source}`} />{NAMES[source]}</div>
            <button className="swap" onClick={swap} aria-label="Đổi chiều dịch" title="Đổi chiều dịch">⇄</button>
            <div className="lang-tab"><span className={`lang-dot ${target}`} />{NAMES[target]}</div>
          </div>
          <div className="panes">
            <div className="pane">
              <label className="sr-only" htmlFor="src">Văn bản {NAMES[source]}</label>
              <textarea id="src" ref={input} value={text} maxLength={1000} lang={source === "vi" ? "vi" : undefined}
                placeholder={source === "vi" ? "Nhập câu tiếng Kinh…" : "Nhập câu tiếng Ê Đê…"}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(); }} />
              {source === "ede" && <EdeKeyboard target={input} onChange={setText} />}
              <div className="pane-foot">
                <span className="muted small">{text.length}/1000 · Ctrl+Enter để dịch</span>
                <span className="spacer" />
                <button className="btn primary" onClick={submit} disabled={!text.trim() || run.isPending}>
                  {run.isPending ? "Đang dịch…" : "Dịch"}
                </button>
              </div>
            </div>
            <div className="pane result-pane" aria-live="polite">
              <div className={`result${result ? "" : " placeholder"}`}>
                {run.isPending ? <span className="spin" /> : result ? result.translated_text : "Bản dịch sẽ hiện ở đây."}
              </div>
              {result && (
                <div className="pane-foot">
                  <Badge status={result.translation_status} />
                  <span className="muted small">{result.seconds}s</span>
                  <span className="spacer" />
                  <button className="icon" title="Sao chép" aria-label="Sao chép bản dịch" onClick={() => {
                    navigator.clipboard.writeText(result.translated_text).then(() => { setCopied(true); setTimeout(() => setCopied(false), 1500); });
                  }}>{copied ? "✓" : "⧉"}</button>
                  <button className="icon" title="Chia sẻ liên kết" aria-label="Sao chép liên kết chia sẻ"
                    onClick={() => navigator.clipboard.writeText(window.location.href)}>↗</button>
                  <button className="link" onClick={() => setFeedback((f) => !f)} aria-expanded={feedback}>Báo lỗi</button>
                </div>
              )}
            </div>
          </div>
          {engine === "gemini" && result?.translation_status === "machine_draft" && result.provenance?.adapter === "nllb" && (
            <p className="alert warn">Gemini không phản hồi nên bản dịch này do mô hình Hriăm tạo ra.</p>
          )}
          <ErrorBox error={run.error} />
        </section>
        <div className="samples">
          <span>Thử:</span>
          {SAMPLES[source].map((s) => <button key={s} onClick={() => { setText(s); run.mutate({ t: s, e: engine }); }}>{s}</button>)}
        </div>
      </div>
      {result && (
        <div className="paper-band">
          <div className="wrap">
            {feedback && <FeedbackForm result={result} onDone={() => setFeedback(false)} />}
            <Details result={result} />
          </div>
        </div>
      )}
    </div>
  );
}

function Details({ result }: { result: Translation }) {
  const notes = result.uncertainty_notes.filter((n) => n.code !== "SHORT_INPUT" || result.translation_status === "machine_draft");
  return (
    <div className="results">
      <div>
        {notes.length > 0 && (
          <ul className="notes" aria-label="Lưu ý">
            {notes.map((n) => <li key={n.code}>{n.message}</li>)}
          </ul>
        )}
        <section className="block">
          <h2>Theo từ điển</h2>
          <p className="hint">Nghĩa của từng từ/cụm trong câu nguồn. Nhãn cho biết nghĩa đã được chuyên gia xác minh hay chưa.</p>
          <div className="gloss">
            {result.lexicon_matches.map((m, i) => (
              <div key={i} className={`tok${m.senses.length ? "" : " miss"}`}>
                <b>{m.term}</b>
                {m.senses.length ? (
                  <>
                    <Link to={`/dictionary/${m.senses[0].entry_id}`}><i>{m.senses[0].text}</i></Link>
                    {m.senses.length > 1 && <div className="alt">{m.senses.slice(1, 4).map((s) => s.text).join(" · ")}</div>}
                    <div><Badge status={m.verified ? "verified" : "draft"} /></div>
                  </>
                ) : <i>chưa có</i>}
              </div>
            ))}
          </div>
        </section>
      </div>
      <aside className="side">
        <section className="block">
          <h2>Câu tương tự</h2>
          {result.similar_examples.length ? (
            <div className="pairs">
              {result.similar_examples.map((e, i) => (
                <div key={i} className={`pair${e.exact ? " exact" : ""}`}>
                  <div><span className="lang">Ê Đê</span>{e.ede}</div>
                  <div><span className="lang">Kinh</span>{e.vi}</div>
                </div>
              ))}
            </div>
          ) : <p className="empty">Chưa có câu ví dụ nào khớp.</p>}
        </section>
        <section className="block">
          <h2>Nguồn bản dịch</h2>
          <p className="hint">
            {result.translation_status === "machine_draft" && (result.provenance?.sends_data_externally
              ? <>Dịch bởi {result.model_version}: văn bản của bạn được gửi tới dịch vụ bên ngoài (Google) để dịch.</>
              : <>Mô hình {result.model_version}, chạy trên máy chủ dự án, không gửi dữ liệu ra ngoài.</>)}
            {result.translation_status === "verified_memory" && <>Câu đã được duyệt trong kho câu song ngữ.</>}
            {result.translation_status === "expert_verified" && <>Mục từ đã được chuyên gia ngôn ngữ xác minh.</>}
            {result.translation_status === "dictionary_example" && <>Câu ví dụ trong từ điển nguồn, chưa được chuyên gia ngôn ngữ xác minh.</>}
            {result.translation_status === "needs_review" &&<>Ghép nghĩa từng từ theo từ điển, chưa theo ngữ pháp.</>}
          </p>
        </section>
      </aside>
    </div>
  );
}

function FeedbackForm({ result, onDone }: { result: Translation; onDone: () => void }) {
  const { user } = useAuth();
  const [errorType, setErrorType] = useState("wrong_meaning");
  const [suggestion, setSuggestion] = useState("");
  const [comment, setComment] = useState("");
  const [publish, setPublish] = useState(false);
  const [research, setResearch] = useState(false);
  const send = useMutation({
    mutationFn: () => api.post("/translations/feedback", {
      source_text: result.source_text, translated_text: result.translated_text, source_language: result.source_language,
      target_language: result.target_language, error_type: errorType, suggested_translation: suggestion || null,
      comment: comment || null, model_version: result.model_version, consent_publish_as_lexicon: publish, consent_research: research,
    }),
  });
  if (!user) return <p className="alert info"><Link to="/login?next=/translate">Đăng nhập</Link> để báo lỗi và đề xuất bản dịch.</p>;
  if (send.isSuccess) return <p className="alert ok">Cảm ơn bạn. {suggestion ? "Đề xuất đã vào hàng chờ duyệt." : "Phản hồi đã được ghi nhận."} <button className="link" onClick={onDone}>Đóng</button></p>;
  return (
    <form className="card form" onSubmit={(e) => { e.preventDefault(); send.mutate(); }}>
      <h2>Báo lỗi bản dịch</h2>
      <label>Loại lỗi
        <select value={errorType} onChange={(e) => setErrorType(e.target.value)}>
          <option value="wrong_meaning">Sai nghĩa</option><option value="omission">Thiếu ý</option>
          <option value="hallucination">Thêm ý không có</option><option value="terminology">Sai thuật ngữ</option>
          <option value="phrase_idiom">Dịch sát chữ thành ngữ/cụm từ</option><option value="dialect">Không đúng phương ngữ</option>
          <option value="spelling">Sai chính tả</option><option value="other">Khác</option>
        </select>
      </label>
      <label>Bản dịch đúng (nếu biết)
        <textarea rows={2} value={suggestion} maxLength={5000} onChange={(e) => setSuggestion(e.target.value)} />
      </label>
      <label>Ghi chú<textarea rows={2} value={comment} maxLength={2000} onChange={(e) => setComment(e.target.value)} /></label>
      {suggestion && (
        <fieldset className="consents">
          <legend>Bạn đồng ý cho Hriăm dùng đề xuất này để (chọn riêng từng mục):</legend>
          <label className="check"><input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} /> Công bố vào kho câu song ngữ sau khi được duyệt</label>
          <label className="check"><input type="checkbox" checked={research} onChange={(e) => setResearch(e.target.checked)} /> Phân tích nghiên cứu ngôn ngữ</label>
        </fieldset>
      )}
      {send.error && <p className="alert error">{errorText(send.error)}</p>}
      <div className="row"><button className="btn primary" disabled={send.isPending}>Gửi</button><button type="button" className="btn ghost" onClick={onDone}>Huỷ</button></div>
    </form>
  );
}
