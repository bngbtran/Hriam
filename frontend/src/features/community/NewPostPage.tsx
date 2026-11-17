import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useRef } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, ErrorBox, PageHead } from "../../components/ui";
import { api } from "../../lib/api";
import type { Post } from "../../lib/types";
import { useCategories } from "./FeedPage";

const schema = z.object({
  category: z.string().min(1, "Chọn danh mục"),
  title: z.string().trim().min(3, "Tiêu đề ít nhất 3 ký tự").max(200),
  body_text: z.string().trim().min(1, "Hãy nhập nội dung").max(20000),
  consent_research_analysis: z.boolean(),
});
type Form = z.infer<typeof schema>;

export function NewPostPage() {
  const cats = useCategories();
  const ref = useRef<HTMLTextAreaElement | null>(null);
  const { register, handleSubmit, setValue, formState: { errors } } = useForm<Form>({
    resolver: zodResolver(schema), defaultValues: { category: "hoi-dap", title: "", body_text: "", consent_research_analysis: false },
  });
  const send = useMutation({ mutationFn: (f: Form) => api.post<Post>("/forum/posts", f) });
  const body = register("body_text");
  if (send.data) {
    const s = send.data.status;
    return (
      <div className="wrap page narrow">
        <PageHead eyebrow="Cộng đồng" title="Đã gửi bài viết" />
        <p><Badge status={s} /></p>
        {s === "published" && <p>Bài đã qua kiểm tra và được đăng. <Link to={`/community/posts/${send.data.id}`}>Xem bài</Link></p>}
        {s === "pending_human_review" && <p>Bài đang chờ người kiểm duyệt xem trực tiếp (thường với nội dung tiếng Ê Đê hoặc có liên kết). Bài chưa hiển thị công khai; bạn sẽ nhận thông báo khi có kết quả. Việc chờ duyệt không tính là vi phạm.</p>}
        {s === "rejected" && <p>Bài chưa được đăng. Xem lý do trong <Link to="/community/my-submissions">Bài của tôi</Link>; bạn có thể sửa hoặc gửi khiếu nại.</p>}
        <p className="row"><Link className="btn ghost" to="/community/my-submissions">Bài của tôi</Link><Link className="btn ghost" to="/community">Về cộng đồng</Link></p>
      </div>
    );
  }
  return (
    <div className="wrap page narrow">
      <PageHead eyebrow="Cộng đồng" title="Viết bài mới">Bài được kiểm duyệt trước khi hiển thị. Đọc <Link to="/rules">quy tắc cộng đồng</Link>.</PageHead>
      <form className="card form" onSubmit={handleSubmit((f) => send.mutate(f))} noValidate>
        <label>Danh mục
          <select {...register("category")}>{cats.data?.map((c) => <option key={c.code} value={c.code}>{c.label}</option>)}</select>
        </label>
        <label>Tiêu đề<input {...register("title")} maxLength={200} aria-invalid={!!errors.title} /></label>
        {errors.title && <p className="field-error">{errors.title.message}</p>}
        <label>Nội dung
          <textarea rows={8} {...body} ref={(el) => { body.ref(el); ref.current = el; }} aria-invalid={!!errors.body_text} />
        </label>
        <EdeKeyboard target={ref} onChange={(v) => setValue("body_text", v, { shouldValidate: true })} />
        {errors.body_text && <p className="field-error">{errors.body_text.message}</p>}
        <fieldset className="consents">
          <legend>Quyền sử dụng (không bắt buộc)</legend>
          <label className="check"><input type="checkbox" {...register("consent_research_analysis")} /> Cho phép dùng bài này để phân tích ngôn ngữ (tìm từ/cụm từ mới). Không dùng để huấn luyện mô hình. Bạn có thể tắt sau.</label>
        </fieldset>
        <ErrorBox error={send.error} />
        <button className="btn primary" disabled={send.isPending}>{send.isPending ? "Đang gửi…" : "Gửi bài"}</button>
      </form>
    </div>
  );
}
