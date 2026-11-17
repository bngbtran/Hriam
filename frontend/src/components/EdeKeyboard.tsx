// Bàn phím ký tự Ê Đê theo orthography profile (docs/04 §4.3): chèn tại vị trí con trỏ, có tên ký tự.
import { useQuery } from "@tanstack/react-query";
import { useState, type RefObject } from "react";
import { api } from "../lib/api";
import type { Profile } from "../lib/types";

type Field = HTMLTextAreaElement | HTMLInputElement;

export function useProfiles() {
  return useQuery({ queryKey: ["orthography"], queryFn: () => api.get<Profile[]>("/orthography/profiles"), staleTime: Infinity });
}

export function insertAtCursor(el: Field, text: string, onChange: (v: string) => void) {
  const start = el.selectionStart ?? el.value.length;
  const end = el.selectionEnd ?? el.value.length;
  const next = el.value.slice(0, start) + text + el.value.slice(end);
  onChange(next);
  requestAnimationFrame(() => { el.focus(); el.setSelectionRange(start + text.length, start + text.length); });
}

export function EdeKeyboard({ target, onChange, compact }: { target: RefObject<Field>; onChange: (v: string) => void; compact?: boolean }) {
  const { data } = useProfiles();
  const [upper, setUpper] = useState(false);
  const profile = data?.[0];
  if (!profile) return null;
  return (
    <div className={`keys${compact ? " compact" : ""}`} role="group" aria-label="Ký tự tiếng Ê Đê">
      <button type="button" className={`shift${upper ? " on" : ""}`} aria-pressed={upper} onClick={() => setUpper((u) => !u)}
        title="Chữ hoa">⇧</button>
      {profile.characters.map((c) => {
        const ch = upper ? c.upper : c.char;
        return (
          <button type="button" key={c.char} title={`${c.name}${c.note ? ` — đọc: ${c.note}` : ""}`} aria-label={c.name}
            onMouseDown={(e) => e.preventDefault()} onClick={() => target.current && insertAtCursor(target.current, ch, onChange)}>
            {ch}
          </button>
        );
      })}
      {profile.status !== "approved" && !compact && (
        <span className="keys-note" title={profile.description}>Bảng chữ nháp v{profile.version}, chờ chuyên gia xác nhận</span>
      )}
    </div>
  );
}
