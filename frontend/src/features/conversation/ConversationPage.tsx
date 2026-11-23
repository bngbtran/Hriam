// Hội thoại theo lượt và phòng hai thiết bị thời gian thực (docs/06 §2.1 & §2.2, docs/07 §10).
import { useMutation, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, Empty, ErrorBox, PageHead, Spinner } from "../../components/ui";
import { ApiError, api, errorText } from "../../lib/api";
import { SPEECH_LANGS, SPEECH_NOTICE, useSpeechToText } from "../../lib/speech";
import { useAuth } from "../../lib/auth";
import type { ConversationRoom, Lang, Translation } from "../../lib/types";

interface Turn {
  id: number;
  speaker: Lang;
  text: string;
  result?: Translation;
  error?: string;
}

interface LiveTurn {
  turn_id: string;
  speaker: Lang;
  speaker_alias: string;
  original_text: string;
  translated_text?: string;
  target_language?: Lang;
  status?: string;
  model_version?: string;
}

const WHO: Record<Lang, string> = { ede: "Người nói tiếng Ê Đê", vi: "Người nói tiếng Kinh" };

function getWsUrl(roomId: string, token: string): string {
  // Vercel không chuyển tiếp WebSocket: khi deploy, đặt VITE_WS_BASE trỏ thẳng tới backend (vd. https://abc-xyz.trycloudflare.com)
  const base = ((import.meta.env.VITE_WS_BASE ?? import.meta.env.VITE_API_BASE) as string | undefined) ?? "";
  let wsOrigin = "";
  if (base.startsWith("http://")) {
    wsOrigin = base.replace("http://", "ws://");
  } else if (base.startsWith("https://")) {
    wsOrigin = base.replace("https://", "wss://");
  } else {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    wsOrigin = `${proto}//${window.location.host}`;
  }
  return `${wsOrigin}/api/v1/realtime/rooms/${roomId}?token=${encodeURIComponent(token)}`;
}

// ----------------------------------------------------
// Chế độ 1 thiết bị & Bộ chuyển đổi tạo phòng
// ----------------------------------------------------
export function ConversationPage() {
  const [activeTab, setActiveTab] = useState<"shared" | "rooms">("shared");

  // State cho chế độ dùng chung một thiết bị
  const [speaker, setSpeaker] = useState<Lang>("vi");
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const ref = useRef<HTMLTextAreaElement>(null);

  // State cho chế độ 2 thiết bị
  const navigate = useNavigate();
  const [joinCode, setJoinCode] = useState("");
  const [endpointing, setEndpointing] = useState<"push_to_talk" | "auto_pause">("push_to_talk");
  const [saveTranscript, setSaveTranscript] = useState(false);
  const [silenceThreshold, setSilenceThreshold] = useState(1500);

  const translate = useMutation({
    mutationFn: (t: Turn) =>
      api.post<Translation>("/translations", {
        text: t.text,
        source_language: t.speaker,
        target_language: t.speaker === "ede" ? "vi" : "ede",
      }),
    onSuccess: (result, t) => setTurns((all) => all.map((x) => (x.id === t.id ? { ...x, result } : x))),
    onError: (e, t) => setTurns((all) => all.map((x) => (x.id === t.id ? { ...x, error: (e as Error).message } : x))),
  });

  const createRoom = useMutation({
    mutationFn: () =>
      api.post<ConversationRoom>("/conversations/rooms", {
        mode: "two_devices",
        endpointing_mode: endpointing,
        silence_threshold_ms: silenceThreshold,
        save_transcript: saveTranscript,
      }),
    onSuccess: (room) => {
      navigate(`/conversation/room/${room.room_code}`);
    },
  });

  function endTurn(spoken?: string) {
    const t = (spoken ?? text).trim();
    if (!t) return;
    const turn = { id: Date.now(), speaker, text: t };
    setTurns((all) => [...all, turn]);
    translate.mutate(turn);
    setText("");
    setSpeaker(speaker === "vi" ? "ede" : "vi"); // luân phiên lượt nói
  }

  // Nhấn giữ để nói (chỉ tiếng Kinh): thả nút là hoàn tất lượt nói
  const sharedSpeech = useSpeechToText((spoken) => endTurn(spoken));

  return (
    <div className="wrap page">
      <PageHead eyebrow="Hội thoại" title="Hội thoại song ngữ Ê Đê – Kinh">
        Hỗ trợ đối thoại trực tiếp giữa người nói tiếng Ê Đê và người nói tiếng Kinh qua dịch tự động hai chiều.
      </PageHead>

      <div className="tabs" style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}>
        <button
          className={`btn ${activeTab === "shared" ? "primary" : "ghost"}`}
          onClick={() => setActiveTab("shared")}
        >
          📱 Một thiết bị (Dùng chung)
        </button>
        <button
          className={`btn ${activeTab === "rooms" ? "primary" : "ghost"}`}
          onClick={() => setActiveTab("rooms")}
        >
          🌐 Hai thiết bị (Phòng thời gian thực)
        </button>
      </div>

      {activeTab === "shared" ? (
        <>
          <div className="alert info">
            Hai người dùng chung một thiết bị, luân phiên nói. Hội thoại không được lưu lại trên máy chủ, chỉ nằm trong bộ nhớ tạm trình duyệt.
          </div>
          <div className="convo">
            <ol className="turns" aria-live="polite">
              {turns.length === 0 && <li className="empty">Chưa có lượt nói nào.</li>}
              {turns.map((t) => (
                <li key={t.id} className={`turn ${t.speaker}`}>
                  <p className="who">{WHO[t.speaker]}</p>
                  <p className="said" lang={t.speaker === "ede" ? "rad" : "vi"}>{t.text}</p>
                  {t.result ? (
                    <p className="translated">
                      {t.result.translated_text} <Badge status={t.result.translation_status} />
                    </p>
                  ) : t.error ? (
                    <p className="field-error">{t.error}</p>
                  ) : (
                    <p className="muted"><span className="spin" /> Đang dịch…</p>
                  )}
                </li>
              ))}
            </ol>
            <div className="card form">
              <div className="seg" role="radiogroup" aria-label="Ai đang nói">
                {(["vi", "ede"] as Lang[]).map((l) => (
                  <button
                    key={l}
                    role="radio"
                    aria-checked={speaker === l}
                    className={speaker === l ? "on" : ""}
                    onClick={() => setSpeaker(l)}
                  >
                    {WHO[l]}
                  </button>
                ))}
              </div>
              <p className="speaking" aria-live="polite">{WHO[speaker]} đang nói</p>
              <label className="sr-only" htmlFor="turn">Lời nói</label>
              <textarea
                id="turn"
                ref={ref}
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    endTurn();
                  }
                }}
                placeholder={speaker === "ede" ? "Nhập câu tiếng Ê Đê…" : "Nhập câu tiếng Kinh…"}
              />
              {speaker === "ede" && <EdeKeyboard target={ref} onChange={setText} compact />}
              {sharedSpeech.listening && <p className="interim" aria-live="polite">{sharedSpeech.interim || "Đang nghe…"}</p>}
              {sharedSpeech.error && <p className="field-error">{sharedSpeech.error}</p>}
              <ErrorBox error={translate.error} />
              <div className="row">
                <button className="btn primary" onClick={() => endTurn()} disabled={!text.trim()}>
                  Hoàn tất lượt nói
                </button>
                <button
                  type="button"
                  className={`btn mic${sharedSpeech.listening ? " live" : ""}`}
                  disabled={!sharedSpeech.supported || !SPEECH_LANGS[speaker]}
                  title={!SPEECH_LANGS[speaker] ? "Trình duyệt chưa nhận dạng được tiếng Ê Đê, hãy nhập bằng chữ" : SPEECH_NOTICE}
                  onPointerDown={(e) => { e.preventDefault(); sharedSpeech.start(speaker); }}
                  onPointerUp={() => sharedSpeech.stop()}
                  onPointerLeave={() => sharedSpeech.listening && sharedSpeech.stop()}
                >
                  <span className="mic-dot" aria-hidden />
                  {sharedSpeech.listening ? "Đang nghe… thả ra" : "Nhấn giữ để nói"}
                </button>
                <span className="spacer" />
                {turns.length > 0 && (
                  <button className="btn ghost" onClick={() => setTurns([])}>
                    Kết thúc & xoá
                  </button>
                )}
              </div>
            </div>
          </div>
        </>
      ) : (
        <div className="grid two-col" style={{ gap: "2rem" }}>
          {/* Card Tham gia phòng */}
          <div className="card">
            <h3>Tham gia phòng bằng mã</h3>
            <p className="muted small">
              Nhập mã gồm 6 ký tự do đối tác cung cấp để kết nối hai máy (docs/06 §2.2).
            </p>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const c = joinCode.trim().toUpperCase();
                if (c.length === 6) navigate(`/conversation/room/${c}`);
              }}
              className="form mt"
            >
              <label htmlFor="join_code_in">Mã phòng (6 ký tự)</label>
              <input
                id="join_code_in"
                type="text"
                maxLength={6}
                placeholder="Ví dụ: AB12CD"
                style={{ fontSize: "1.25rem", letterSpacing: "2px", textTransform: "uppercase" }}
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
                required
              />
              <button
                type="submit"
                className="btn primary mt"
                disabled={joinCode.trim().length !== 6}
              >
                Vào phòng hội thoại
              </button>
            </form>
          </div>

          {/* Card Tạo phòng mới */}
          <div className="card">
            <h3>Tạo phòng hội thoại mới</h3>
            <p className="muted small">
              Tạo phòng kết nối thời gian thực qua WebSocket, hỗ trợ phụ đề trực tiếp hai chiều.
            </p>
            <div className="form mt">
              <label htmlFor="ep_mode">Chế độ ngắt câu (Endpointing)</label>
              <select
                id="ep_mode"
                value={endpointing}
                onChange={(e) => setEndpointing(e.target.value as any)}
              >
                <option value="push_to_talk">Nhấn giữ để nói (Push-to-Talk) - Đề xuất</option>
                <option value="auto_pause">Tự động nhận diện khoảng lặng (Auto-pause VAD)</option>
              </select>

              {endpointing === "auto_pause" && (
                <div>
                  <label htmlFor="sil_th">Ngưỡng ngắt câu ({silenceThreshold / 1000}s)</label>
                  <input
                    id="sil_th"
                    type="range"
                    min={1000}
                    max={2500}
                    step={100}
                    value={silenceThreshold}
                    onChange={(e) => setSilenceThreshold(Number(e.target.value))}
                  />
                </div>
              )}

              <label className="check mt">
                <input
                  type="checkbox"
                  checked={saveTranscript}
                  onChange={(e) => setSaveTranscript(e.target.checked)}
                />
                Lưu lại biên bản hội thoại trên máy chủ (mặc định tắt vì quyền riêng tư)
              </label>

              <ErrorBox error={createRoom.error} />

              <button
                type="button"
                className="btn primary mt"
                onClick={() => createRoom.mutate()}
                disabled={createRoom.isPending}
              >
                {createRoom.isPending ? "Đang tạo phòng…" : "Tạo mã phòng mới"}
              </button>
            </div>
          </div>
        </div>
      )}

      <p className="muted small mt">
        Chế độ hội thoại tuân thủ nguyên tắc không lưu trữ giọng nói nếu không có sự đồng ý rõ ràng.{" "}
        <Link to="/privacy">Chính sách quyền riêng tư</Link>
      </p>
    </div>
  );
}

// ----------------------------------------------------
// Màn hình Phòng Hội thoại Hai thiết bị (Realtime)
// ----------------------------------------------------
export function RoomPage() {
  const { roomCode } = useParams<{ roomCode: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();

  const [alias, setAlias] = useState(user?.display_name || "Khách");
  const [myLang, setMyLang] = useState<Lang>("vi");
  const [ticket, setTicket] = useState<string | null>(null);

  // WebSocket state
  const [wsConnected, setWsConnected] = useState(false);
  const [participants, setParticipants] = useState<{ alias: string; language?: string }[]>([]);
  const [liveTurns, setLiveTurns] = useState<LiveTurn[]>([]);
  const [peerTyping, setPeerTyping] = useState<string | null>(null);

  // Turn input
  const [inputText, setInputText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const turnsEndRef = useRef<HTMLDivElement>(null);

  // Lấy thông tin phòng qua REST
  const roomQuery = useQuery({
    queryKey: ["room", roomCode],
    queryFn: () => api.get<ConversationRoom>(`/conversations/rooms/code/${roomCode}`),
    enabled: !!roomCode,
    retry: false,
  });

  // Lấy vé tham gia (JWT join token)
  const joinMutation = useMutation({
    mutationFn: () =>
      api.post<{ token: string; room_id: string }>(
        `/conversations/rooms/${roomQuery.data?.id}/join-token`,
        { participant_alias: alias.trim() || "Khách", language_preference: myLang }
      ),
    onSuccess: (data) => {
      setTicket(data.token);
    },
  });

  // Tự động cuộn xuống cuối khi có tin nhắn mới
  useEffect(() => {
    turnsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [liveTurns]);

  // Kết nối WebSocket khi có ticket
  useEffect(() => {
    if (!ticket || !roomQuery.data?.id) return;

    const wsUrl = getWsUrl(roomQuery.data.id, ticket);
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        const type = msg.type;
        const payload = msg.payload || {};

        if (type === "participant.joined") {
          setParticipants((prev) => [...prev.filter((p) => p.alias !== payload.alias), payload]);
        } else if (type === "participant.left") {
          setParticipants((prev) => prev.filter((p) => p.alias !== payload.alias));
        } else if (type === "turn.started") {
          setPeerTyping(`${payload.alias || "Đối tác"} đang nói...`);
        } else if (type === "transcript.final") {
          setPeerTyping(null);
          setLiveTurns((prev) => {
            const existing = prev.find((t) => t.turn_id === msg.turn_id);
            if (existing) {
              return prev.map((t) =>
                t.turn_id === msg.turn_id
                  ? { ...t, original_text: payload.text, speaker: payload.language, speaker_alias: payload.alias }
                  : t
              );
            }
            return [
              ...prev,
              {
                turn_id: msg.turn_id,
                speaker: payload.language,
                speaker_alias: payload.alias,
                original_text: payload.text,
              },
            ];
          });
        } else if (type === "translation.final") {
          setLiveTurns((prev) =>
            prev.map((t) =>
              t.turn_id === msg.turn_id
                ? {
                    ...t,
                    translated_text: payload.text,
                    target_language: payload.target_language,
                    status: payload.status,
                    model_version: payload.model_version,
                  }
                : t
            )
          );
        } else if (type === "turn.completed") {
          setPeerTyping(null);
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onclose = () => {
      setWsConnected(false);
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "room.leave" }));
        ws.close();
      }
    };
  }, [ticket, roomQuery.data?.id]);

  // Gửi một lượt nói qua WebSocket
  const sendText = useCallback((value: string) => {
    const textToSend = value.trim();
    if (!textToSend || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
    wsRef.current.send(JSON.stringify({ type: "turn.text", payload: { text: textToSend, language: myLang } }));
    setInputText("");
  }, [myLang]);
  const sendTurn = useCallback(() => sendText(inputText), [sendText, inputText]);

  // Nhấn giữ để nói: nhận dạng giọng nói của trình duyệt, thả nút thì gửi câu đã nhận dạng
  const speech = useSpeechToText(sendText);
  const canSpeak = speech.supported && !!SPEECH_LANGS[myLang] && wsConnected;
  const startRecording = () => {
    if (!canSpeak) return;
    speech.start(myLang);
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "turn.start", payload: { language: myLang } }));
    }
  };
  const stopRecording = () => speech.stop();

  // Đọc to bản dịch qua Web Speech API
  const speakText = (text: string, lang: string) => {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === "vi" ? "vi-VN" : "en-US";
    window.speechSynthesis.speak(utterance);
  };

  if (roomQuery.isLoading) {
    return (
      <div className="wrap page narrow">
        <Spinner label="Đang kiểm tra mã phòng…" />
      </div>
    );
  }

  if (roomQuery.error || !roomQuery.data) {
    return (
      <div className="wrap page narrow">
        {roomQuery.error instanceof ApiError && roomQuery.error.status !== 404 ? (
          <PageHead eyebrow="Lỗi phòng" title="Không mở được phòng">
            {errorText(roomQuery.error)}
          </PageHead>
        ) : (
          <PageHead eyebrow="Lỗi phòng" title="Không tìm thấy phòng">
            Mã phòng <b>{roomCode}</b> không tồn tại, đã kết thúc hoặc đã hết hạn (phòng tồn tại 24 giờ).
          </PageHead>
        )}
        <button className="btn primary mt" onClick={() => navigate("/conversation")}>
          Quay lại tạo phòng mới
        </button>
      </div>
    );
  }

  const room = roomQuery.data;

  // Chưa có ticket -> màn hình nhập thông tin tham gia
  if (!ticket) {
    return (
      <div className="wrap page narrow">
        <PageHead eyebrow="Phòng hai thiết bị" title={`Phòng: ${room.room_code}`}>
          Mã phòng hoạt động đến {new Date(room.expires_at).toLocaleTimeString("vi-VN")}. Chọn thông tin của bạn để kết nối.
        </PageHead>

        <div className="card mt form">
          <label htmlFor="p_alias">Tên hoặc bí danh của bạn</label>
          <input
            id="p_alias"
            type="text"
            value={alias}
            onChange={(e) => setAlias(e.target.value)}
            placeholder="Ví dụ: Y Bhi, H'Ngọc, Tuấn…"
            required
          />

          <label className="mt">Ngôn ngữ bạn sử dụng</label>
          <div className="seg" role="radiogroup">
            <button
              type="button"
              role="radio"
              aria-checked={myLang === "vi"}
              className={myLang === "vi" ? "on" : ""}
              onClick={() => setMyLang("vi")}
            >
              Tiếng Kinh (Việt)
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={myLang === "ede"}
              className={myLang === "ede" ? "on" : ""}
              onClick={() => setMyLang("ede")}
            >
              Tiếng Ê Đê (Kleĉ Êđê)
            </button>
          </div>

          <ErrorBox error={joinMutation.error} />

          <button
            type="button"
            className="btn primary mt"
            onClick={() => joinMutation.mutate()}
            disabled={joinMutation.isPending || !alias.trim()}
          >
            {joinMutation.isPending ? "Đang tham gia…" : "Bắt đầu kết nối"}
          </button>
        </div>
      </div>
    );
  }

  // Màn hình hội thoại thời gian thực trực tiếp
  return (
    <div className="wrap page" style={{ maxWidth: "860px" }}>
      {/* Header phòng */}
      <div className="card mb" style={{ padding: "0.75rem 1.25rem" }}>
        <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
          <div className="row" style={{ gap: "0.75rem", alignItems: "center" }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: wsConnected ? "#10b981" : "#ef4444",
                display: "inline-block",
              }}
              title={wsConnected ? "Đã kết nối thời gian thực" : "Mất kết nối"}
            />
            <span style={{ fontSize: "1.2rem", fontWeight: "bold", letterSpacing: "1px" }}>
              Mã phòng: {room.room_code}
            </span>
            <button
              className="btn ghost small"
              onClick={() => {
                navigator.clipboard.writeText(window.location.href);
                alert("Đã sao chép liên kết phòng vào bộ nhớ tạm!");
              }}
            >
              📋 Sao chép link
            </button>
          </div>

          <div className="row" style={{ gap: "0.5rem" }}>
            <span className="badge muted">
              Bạn: <b>{alias}</b> ({myLang === "ede" ? "Ê Đê" : "Kinh"}) {participants.length > 0 ? `· ${participants.length + 1} người` : ""}
            </span>
            <button
              className="btn ghost small danger"
              onClick={() => {
                wsRef.current?.close();
                navigate("/conversation");
              }}
            >
              Rời phòng
            </button>
          </div>
        </div>

        {peerTyping && (
          <p className="muted small mt" style={{ fontStyle: "italic" }}>
            💬 {peerTyping}
          </p>
        )}
      </div>

      {/* Danh sách lượt nói & Phụ đề trực tiếp */}
      <div
        className="card"
        style={{
          minHeight: "350px",
          maxHeight: "55vh",
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
          padding: "1.25rem",
          background: "var(--surface-sunken)",
        }}
      >
        {liveTurns.length === 0 ? (
          <Empty motif="hoa-van">
            <p>Phòng đã sẵn sàng. Hãy bắt đầu nói hoặc nhập văn bản bên dưới.</p>
          </Empty>
        ) : (
          liveTurns.map((turn) => {
            const isMe = turn.speaker_alias === alias;
            return (
              <div
                key={turn.turn_id}
                style={{
                  alignSelf: isMe ? "flex-end" : "flex-start",
                  maxWidth: "80%",
                  background: isMe ? "var(--primary-subtle, #e0f2fe)" : "var(--surface, #ffffff)",
                  border: "1px solid var(--border)",
                  borderRadius: "10px",
                  padding: "0.75rem 1rem",
                }}
              >
                <div className="row small muted" style={{ justifyContent: "space-between", marginBottom: "0.25rem" }}>
                  <span><b>{turn.speaker_alias}</b> ({WHO[turn.speaker]})</span>
                  {turn.status && <Badge status={turn.status} />}
                </div>

                {/* Câu gốc */}
                <p style={{ margin: "0.25rem 0", fontSize: "1.05rem" }} lang={turn.speaker === "ede" ? "rad" : "vi"}>
                  {turn.original_text}
                </p>

                {/* Phụ đề dịch thời gian thực */}
                {turn.translated_text ? (
                  <div
                    style={{
                      borderTop: "1px dashed var(--border)",
                      marginTop: "0.5rem",
                      paddingTop: "0.5rem",
                      color: "var(--primary)",
                      fontWeight: 500,
                    }}
                  >
                    <span>{turn.translated_text}</span>
                    <button
                      className="btn ghost small"
                      style={{ marginLeft: "0.5rem", padding: "0 4px", fontSize: "0.8rem" }}
                      title="Đọc to bản dịch"
                      onClick={() => speakText(turn.translated_text!, turn.target_language || "vi")}
                    >
                      🔊
                    </button>
                  </div>
                ) : (
                  <p className="muted small mt">
                    <span className="spin" /> Đang dịch thời gian thực…
                  </p>
                )}
              </div>
            );
          })
        )}
        <div ref={turnsEndRef} />
      </div>

      {/* Khu vực nhập câu & Phím Push-to-Talk */}
      <div className="card mt form">
        <label htmlFor="room_turn_input" className="sr-only">Nhập nội dung lượt nói</label>
        <textarea
          id="room_turn_input"
          ref={inputRef}
          rows={3}
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendTurn();
            }
          }}
          placeholder={
            myLang === "ede"
              ? "Nhập câu tiếng Ê Đê (nhấn Enter để gửi)…"
              : "Nhập câu tiếng Kinh (nhấn Enter để gửi)…"
          }
        />

        {myLang === "ede" && <EdeKeyboard target={inputRef} onChange={setInputText} compact />}
        {speech.listening && <p className="interim" aria-live="polite">{speech.interim || "Đang nghe…"}</p>}
        {speech.error && <p className="field-error">{speech.error}</p>}
        <p className="muted small speech-note">
          {SPEECH_LANGS[myLang] ? SPEECH_NOTICE : "Nhận dạng giọng nói chưa hỗ trợ tiếng Ê Đê; hãy nhập bằng chữ."}
        </p>

        <div className="row mt" style={{ justifyContent: "space-between", alignItems: "center" }}>
          {/* Nút Push-to-talk */}
          <button
            type="button"
            className={`btn mic${speech.listening ? " live" : ""}`}
            disabled={!canSpeak}
            title={!SPEECH_LANGS[myLang] ? "Trình duyệt chưa nhận dạng được tiếng Ê Đê, hãy nhập bằng chữ" :
              !speech.supported ? "Trình duyệt này không hỗ trợ nhận dạng giọng nói (dùng Chrome hoặc Edge)" : SPEECH_NOTICE}
            onPointerDown={(e) => { e.preventDefault(); startRecording(); }}
            onPointerUp={stopRecording}
            onPointerLeave={() => speech.listening && stopRecording()}
          >
            <span className="mic-dot" aria-hidden />
            {speech.listening ? "Đang nghe… thả ra để gửi" : "Nhấn giữ để nói"}
          </button>

          <button
            type="button"
            className="btn primary"
            onClick={sendTurn}
            disabled={!inputText.trim()}
          >
            Gửi lượt nói (Enter)
          </button>
        </div>
      </div>
    </div>
  );
}
