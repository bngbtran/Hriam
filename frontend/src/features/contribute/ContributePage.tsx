// Contribution Center (docs/01 §4.5): đóng góp vào vùng chờ duyệt, consent tách theo mục đích.
import { zodResolver } from "@hookform/resolvers/zod";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import { Link, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, Empty, ErrorBox, LoadMore, LoginPrompt, PageHead, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Contribution } from "../../lib/types";

const TYPES = {
  word: ["Từ mới", "Từ Ê Đê chưa có trong từ điển"],
  sense: ["Nghĩa khác", "Nghĩa khác của một từ đã có"],
  phrase: ["Cụm từ / thành ngữ", "Cụm nhiều từ, thành ngữ, tục ngữ"],
  sentence_pair: ["Cặp câu", "Câu Ê Đê và bản dịch tiếng Kinh"],
  correction: ["Sửa lỗi", "Báo sai chính tả hoặc nghĩa của mục từ"],
} as const;
type Kind = keyof typeof TYPES;

const schema = z.object({
  submission_type: z.enum(["word", "sense", "phrase", "sentence_pair", "correction"]),
  ede_form: z.string().trim().min(1, "Hãy nhập tiếng Ê Đê").max(2000),
  proposed_vi_meaning: z.string().trim().max(2000),
  context_text: z.string().max(2000),
  phrase_type: z.string(),
  source_note: z.string().max(1000),
  publish_as_lexicon: z.boolean(), use_for_research: z.boolean(), use_for_model_training: z.boolean(),
}).refine((f) => f.submission_type === "correction" || f.proposed_vi_meaning.length > 0,
  { path: ["proposed_vi_meaning"], message: "Hãy nhập nghĩa hoặc bản dịch tiếng Kinh" });
type Form = z.infer<typeof schema>;

export function ContributePage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const qc = useQueryClient();
  const ref = useRef<HTMLInputElement | null>(null);
  const initialType = (params.get("type") as Kind) in TYPES ? (params.get("type") as Kind) : "word";
  const { register, handleSubmit, watch, setValue, reset, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { submission_type: initialType, ede_form: params.get("form") ?? "", proposed_vi_meaning: "", context_text: "",
      phrase_type: "unknown", source_note: "", publish_as_lexicon: true, use_for_research: false, use_for_model_training: false },
  });
  const kind = watch("submission_type");
  const send = useMutation({
    mutationFn: (f: Form) => api.post<Contribution>("/contributions", {
      submission_type: f.submission_type, ede_form: f.ede_form, proposed_vi_meaning: f.proposed_vi_meaning || null,
      context_text: f.context_text || null, phrase_type: f.submission_type === "phrase" ? f.phrase_type : null,
      target_entry_id: params.get("entry"), source_note: f.source_note || null,
      consents: { publish_as_lexicon: f.publish_as_lexicon, use_for_research: f.use_for_research, use_for_model_training: f.use_for_model_training },
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-contributions"] }); reset(); },
  });
  const ede = register("ede_form");
  return (
    <div className="wrap page">
      <PageHead eyebrow="Đóng góp" title="Cùng làm giàu tiếng Ê Đê">
        Đóng góp được lưu riêng, chưa vào từ điển chính thức cho đến khi chuyên gia ngôn ngữ hoặc quản trị viên duyệt.
        Nếu bị từ chối, nội dung sẽ được xoá khỏi hệ thống.
      </PageHead>
      {!user ? <LoginPrompt action="gửi đóng góp" /> : (
        <div className="two-col">
          <form className="card form" onSubmit={handleSubmit((f) => send.mutate(f))} noValidate>
            <fieldset className="type-pick">
              <legend>Loại đóng góp</legend>
              {(Object.keys(TYPES) as Kind[]).map((k) => (
                <label key={k} className={`pick${kind === k ? " on" : ""}`}>
                  <input type="radio" value={k} {...register("submission_type")} />
                  <b>{TYPES[k][0]}</b><small>{TYPES[k][1]}</small>
                </label>
              ))}
            </fieldset>
            <label>{kind === "sentence_pair" ? "Câu tiếng Ê Đê" : "Từ / cụm tiếng Ê Đê"}
              <input lang="rad" {...ede} ref={(el) => { ede.ref(el); ref.current = el; }} aria-invalid={!!errors.ede_form} />
            </label>
            <EdeKeyboard target={ref} onChange={(v) => setValue("ede_form", v, { shouldValidate: true })} compact />
            {errors.ede_form && <p className="field-error">{errors.ede_form.message}</p>}
            {kind === "phrase" && (
              <label>Loại cụm (giả thuyết, chuyên gia sẽ xác định)
                <select {...register("phrase_type")}>
                  <option value="unknown">Chưa rõ</option><option value="collocation">Kết hợp thường gặp</option>
                  <option value="phrase">Cụm từ</option><option value="verb_phrase">Cụm động từ</option>
                  <option value="idiom">Thành ngữ</option><option value="proverb">Tục ngữ</option>
                </select>
              </label>
            )}
            <label>{kind === "sentence_pair" ? "Bản dịch tiếng Kinh" : kind === "correction" ? "Nội dung đúng (nếu biết)" : "Nghĩa tiếng Kinh"}
              <input {...register("proposed_vi_meaning")} aria-invalid={!!errors.proposed_vi_meaning} />
            </label>
            {errors.proposed_vi_meaning && <p className="field-error">{errors.proposed_vi_meaning.message}</p>}
            {kind !== "sentence_pair" && (
              <label>Câu ví dụ (dạng “câu Ê Đê | bản dịch”) hoặc ngữ cảnh
                <input {...register("context_text")} placeholder="Adŭ hriăm | Phòng học" />
              </label>
            )}
            <label>Nguồn, phương ngữ, địa phương<input {...register("source_note")} placeholder="Ví dụ: người lớn tuổi ở Buôn Ma Thuột" /></label>
            <fieldset className="consents">
              <legend>Bạn đồng ý cho Hriăm (chọn riêng từng mục):</legend>
              <label className="check"><input type="checkbox" {...register("publish_as_lexicon")} /> Công bố vào từ điển/kho câu sau khi được duyệt (bắt buộc để có thể duyệt)</label>
              <label className="check"><input type="checkbox" {...register("use_for_research")} /> Dùng cho nghiên cứu, phân tích ngôn ngữ</label>
              <label className="check"><input type="checkbox" {...register("use_for_model_training")} /> Dùng để huấn luyện mô hình dịch</label>
            </fieldset>
            <ErrorBox error={send.error} />
            {send.data && (
              <div className="alert ok">
                Đã gửi, đang chờ duyệt.
                {send.data.duplicates?.entries.length ? <> Lưu ý: từ điển đã có {send.data.duplicates.entries.map((e) => <Link key={e.id} to={`/dictionary/${e.id}`}> {e.canonical_form}</Link>)}.</> : null}
                {send.data.duplicates?.pending ? <> Có {send.data.duplicates.pending} đóng góp tương tự đang chờ.</> : null}
              </div>
            )}
            <button className="btn primary" disabled={send.isPending}>{send.isPending ? "Đang gửi…" : "Gửi đóng góp"}</button>
            <p className="muted small">Đóng góp âm thanh sẽ mở khi có quy trình đồng ý và lưu trữ riêng.</p>
          </form>
          <MyContributions />
        </div>
      )}
    </div>
  );
}

function MyContributions() {
  const qc = useQueryClient();
  const q = useInfiniteQuery({
    queryKey: ["my-contributions"],
    queryFn: ({ pageParam }) => api.page<Contribution[]>("/contributions/mine", { cursor: pageParam }),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (last) => last.meta.next_cursor ?? undefined,
  });
  const withdraw = useMutation({ mutationFn: (id: string) => api.del(`/contributions/${id}`), onSuccess: () => qc.invalidateQueries({ queryKey: ["my-contributions"] }) });
  const rows = q.data?.pages.flatMap((p) => p.data) ?? [];
  return (
    <section>
      <h2>Đóng góp của tôi</h2>
      {rows.length === 0 ? <Empty motif="than-lan">Bạn chưa gửi đóng góp nào.</Empty> : (
        <ul className="list">
          {rows.map((c) => (
            <li key={c.id} className="list-item">
              <div className="row-between"><b lang="rad">{c.purged ? "(nội dung đã xoá)" : c.ede_form}</b><Badge status={c.status} /></div>
              {!c.purged && <p className="muted">{c.proposed_vi_meaning}</p>}
              <p className="muted small">{TYPES[c.submission_type as Kind]?.[0] ?? c.submission_type} · {fmtDate(c.created_at)}
                {c.decision_code && ` · mã quyết định: ${c.decision_code}`}</p>
              {c.result_entry_id && <Link to={`/dictionary/${c.result_entry_id}`}>Xem trong từ điển</Link>}
              {c.status === "pending" && <button className="link small" onClick={() => withdraw.mutate(c.id)}>Rút đóng góp</button>}
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasMore={!!q.hasNextPage} onClick={() => q.fetchNextPage()} />
    </section>
  );
}
