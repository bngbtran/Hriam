import { useQuery } from "@tanstack/react-query";
import { ErrorBox, PageHead, Spinner } from "../../components/ui";
import { api } from "../../lib/api";

export function AdminCandidates() {
  const q = useQuery({ queryKey: ["candidates"], queryFn: () => api.page<unknown[]>("/admin/lexical-candidates") });
  if (q.isLoading) return <Spinner />;
  return (
    <>
      <PageHead eyebrow="Quản trị" title="Ứng viên từ/nghĩa/cụm do AI phát hiện" />
      <ErrorBox error={q.error} />
      <p className="alert info">{String(q.data?.meta.message ?? "")}</p>
      <p className="muted">Khi triển khai, mỗi ứng viên sẽ có các lần xuất hiện, nhóm ngữ cảnh, bằng chứng ủng hộ/mâu thuẫn và mức bằng chứng riêng
        cho từng nghĩa/cụm. Hệ thống chỉ phân tích bài đã đăng mà tác giả cho phép phân tích ngôn ngữ, và không tự đưa vào từ điển.</p>
    </>
  );
}
