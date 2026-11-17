import { useInfiniteQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, Empty, ErrorBox, LoadMore, PageHead, Spinner } from "../../components/ui";
import { api } from "../../lib/api";
import type { EntrySummary } from "../../lib/types";

export function DictionaryPage() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [lang, setLang] = useState(params.get("lang") ?? "auto");
  const [debounced, setDebounced] = useState(q);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const t = setTimeout(() => { setDebounced(q); setParams(q ? { q, lang } : {}, { replace: true }); }, 250);
    return () => clearTimeout(t);
  }, [q, lang, setParams]);
  const query = useInfiniteQuery({
    queryKey: ["lexicon", debounced, lang],
    queryFn: ({ pageParam }) => api.page<EntrySummary[]>("/lexicon/search", { q: debounced, lang, cursor: pageParam, limit: 24 }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.meta.next_cursor ?? undefined,
  });
  const rows = query.data?.pages.flatMap((p) => p.data) ?? [];
  return (
    <div className="wrap page">
      <PageHead eyebrow="Từ điển" title="Từ điển Ê Đê – tiếng Kinh">
        Tra theo từ Ê Đê hoặc theo nghĩa tiếng Kinh. Nghĩa “Chưa xác minh” lấy từ từ điển nguồn, chờ chuyên gia ngôn ngữ rà soát.
      </PageHead>
      <div className="search-row">
        <div className="search">
          <label className="sr-only" htmlFor="q">Tìm từ</label>
          <input id="q" ref={input} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ví dụ: adŭ, ăn, nhà…" autoComplete="off" />
        </div>
        <div className="seg" role="radiogroup" aria-label="Tìm theo">
          {[["auto", "Cả hai"], ["ede", "Từ Ê Đê"], ["vi", "Nghĩa tiếng Kinh"]].map(([v, l]) => (
            <button key={v} role="radio" aria-checked={lang === v} className={lang === v ? "on" : ""} onClick={() => setLang(v)}>{l}</button>
          ))}
        </div>
      </div>
      <EdeKeyboard target={input} onChange={setQ} compact />
      <ErrorBox error={query.error} />
      {query.isLoading ? <Spinner /> : rows.length === 0 ? <Empty>Không tìm thấy mục từ. Bạn có thể <Link to="/contribute">đóng góp từ mới</Link>.</Empty> : (
        <div className="cards grid">
          {rows.map((e) => (
            <Link key={e.id} to={`/dictionary/${e.id}`} className="card link-card">
              <h3>{e.canonical_form}</h3>
              <span className="pos">{[e.part_of_speech, e.entry_type !== "word" ? "cụm từ" : null].filter(Boolean).join(" · ")}</span>
              <ol>{e.senses.slice(0, 3).map((s) => <li key={s.id}>{s.definition_vi} {s.status === "verified" && <Badge status="verified" />}</li>)}</ol>
              {e.variants.length > 0 && <p className="muted small">Biến thể: {e.variants.join(", ")}</p>}
            </Link>
          ))}
        </div>
      )}
      <div className="center"><LoadMore hasMore={!!query.hasNextPage} loading={query.isFetchingNextPage} onClick={() => query.fetchNextPage()} /></div>
    </div>
  );
}
