import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Badge, ErrorBox, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import type { EntryDetail } from "../../lib/types";

const TYPES: Record<string, string> = { word: "Từ", multiword_expression: "Cụm từ", idiom: "Thành ngữ", proverb: "Tục ngữ", phrase: "Cụm", other: "Khác" };

export function EntryPage() {
  const { entryId } = useParams();
  const q = useQuery({ queryKey: ["entry", entryId], queryFn: () => api.get<EntryDetail>(`/lexicon/entries/${entryId}`) });
  if (q.isLoading) return <div className="wrap page"><Spinner /></div>;
  if (!q.data) return <div className="wrap page"><ErrorBox error={q.error} /></div>;
  const e = q.data;
  return (
    <div className="wrap page narrow">
      <p><Link to="/dictionary">← Từ điển</Link></p>
      <article className="card entry">
        <p className="eyebrow dark">{TYPES[e.entry_type] ?? e.entry_type}{e.part_of_speech && ` · ${e.part_of_speech}`}{e.loan_source && ` · gốc ${e.loan_source}`}</p>
        <h1 className="entry-title" lang="rad">{e.canonical_form}</h1>
        {e.forms.length > 0 && <p className="muted">Biến thể: {e.forms.map((f) => f.form_text).join(", ")}</p>}
        <ol className="senses">
          {e.senses.map((s) => (
            <li key={s.id}>
              <div className="sense-head"><strong>{s.definition_vi}</strong> <Badge status={s.status} /></div>
              {s.definition_ede && <p lang="rad">{s.definition_ede}</p>}
              {[s.part_of_speech, s.semantic_domain, s.usage_register, s.literal_or_figurative].some(Boolean) &&
                <p className="muted small">{[s.part_of_speech, s.semantic_domain, s.usage_register, s.literal_or_figurative].filter(Boolean).join(" · ")}</p>}
              {s.examples.length > 0 && (
                <ul className="examples">
                  {s.examples.map((x, i) => <li key={i}><em lang="rad">{x.ede}</em> — {x.vi}</li>)}
                </ul>
              )}
            </li>
          ))}
        </ol>
        {e.notes && <p className="muted small">Ghi chú: {e.notes}</p>}
        <dl className="prov">
          <div><dt>Nguồn</dt><dd>{e.provenance.source?.name ?? "—"}{e.provenance.source_ref && ` (${e.provenance.source_ref})`}</dd></div>
          <div><dt>Giấy phép</dt><dd>{e.provenance.license ? <>{e.provenance.license.name} <Badge status={e.provenance.license.review_status === "approved" ? "approved" : "pending"} /></> : "—"}</dd></div>
          <div><dt>Cập nhật</dt><dd>{fmtDate(e.provenance.updated_at)}</dd></div>
        </dl>
        <p className="row">
          <Link className="btn ghost" to={`/translate?from=ede&text=${encodeURIComponent(e.canonical_form)}`}>Dịch thử</Link>
          <Link className="btn ghost" to={`/contribute?type=sense&entry=${e.id}&form=${encodeURIComponent(e.canonical_form)}`}>Đề xuất nghĩa khác</Link>
          <Link className="btn ghost" to={`/contribute?type=correction&entry=${e.id}&form=${encodeURIComponent(e.canonical_form)}`}>Báo sai</Link>
        </p>
      </article>
    </div>
  );
}
