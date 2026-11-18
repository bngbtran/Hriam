// Nhận dạng giọng nói bằng Web Speech API của trình duyệt (Chrome, Edge, Safari).
// Chỉ có tiếng Kinh (vi-VN): trình duyệt chưa có tiếng Ê Đê. Trên Chrome, âm thanh được gửi tới dịch vụ của Google
// để nhận dạng (docs/08 §6: phải báo rõ cho người dùng). Hriăm không lưu âm thanh.
import { useCallback, useEffect, useRef, useState } from "react";

type Recognition = {
  lang: string; continuous: boolean; interimResults: boolean;
  start: () => void; stop: () => void; abort: () => void;
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
};

function factory(): (new () => Recognition) | null {
  const w = window as unknown as { SpeechRecognition?: new () => Recognition; webkitSpeechRecognition?: new () => Recognition };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export const SPEECH_LANGS: Record<string, string | null> = { vi: "vi-VN", ede: null };
export const SPEECH_NOTICE = "Giọng nói tiếng Kinh được nhận dạng bằng dịch vụ của trình duyệt (Chrome gửi âm thanh tới Google). Hriăm không lưu âm thanh.";

const ERRORS: Record<string, string> = {
  "not-allowed": "Trình duyệt chưa cho phép dùng micro.",
  "service-not-allowed": "Trình duyệt chưa cho phép dùng micro.",
  "no-speech": "Không nghe thấy giọng nói, hãy thử lại.",
  "audio-capture": "Không tìm thấy micro.",
  network: "Không kết nối được dịch vụ nhận dạng giọng nói.",
};

/** Nhấn giữ để nói: start() khi nhấn, stop() khi thả; onFinal nhận câu cuối cùng. */
export function useSpeechToText(onFinal: (text: string) => void) {
  const Ctor = typeof window !== "undefined" ? factory() : null;
  const rec = useRef<Recognition | null>(null);
  const finalText = useRef("");
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  useEffect(() => () => rec.current?.abort(), []);

  const start = useCallback((lang: string) => {
    const code = SPEECH_LANGS[lang];
    if (!Ctor || !code || rec.current) return;
    const r = new Ctor();
    r.lang = code;
    r.continuous = true;
    r.interimResults = true;
    finalText.current = "";
    setInterim("");
    setError(null);
    r.onresult = (e) => {
      let live = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) finalText.current += res[0].transcript;
        else live += res[0].transcript;
      }
      setInterim((finalText.current + live).trim());
    };
    r.onerror = (e) => { if (e.error !== "aborted") setError(ERRORS[e.error] ?? "Lỗi nhận dạng giọng nói."); };
    r.onend = () => {
      rec.current = null;
      setListening(false);
      const text = finalText.current.trim();
      setInterim("");
      if (text) onFinalRef.current(text);
    };
    rec.current = r;
    try {
      r.start();
      setListening(true);
    } catch {
      rec.current = null;
    }
  }, [Ctor]);

  const stop = useCallback(() => rec.current?.stop(), []);

  return { supported: !!Ctor, listening, interim, error, start, stop };
}
