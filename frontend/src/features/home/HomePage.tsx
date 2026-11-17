// Trang chủ (docs/01 §4.1): mục tiêu bảo tồn, lối vào nhanh, liên kết quy tắc/quyền riêng tư.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../lib/api";

const ENTRIES = [
  ["/translate", "Dịch thuật", "Ê Đê ↔ tiếng Kinh, kèm trạng thái xác minh.", "qua-tram"],
  ["/dictionary", "Từ điển", "Gần 3.900 mục từ, nhiều nghĩa, ví dụ và nguồn.", "rang-cua"],
  ["/conversation", "Hội thoại", "Hai người, một thiết bị, lần lượt từng câu.", "chuon-chuon"],
  ["/community", "Cộng đồng", "Hỏi đáp, phát âm, phương ngữ, góp ý bản dịch.", "rua"],
  ["/culture", "Văn hoá", "Kho tư liệu theo quyền của cộng đồng.", "than-lan"],
] as const;

export function HomePage() {
  const nav = useNavigate();
  const [text, setText] = useState("");
  const stats = useQuery({ queryKey: ["stats"], queryFn: () => api.get<{ entries: number; senses: number; verified_senses: number; examples: number }>("/lexicon/stats") });
  const fmt = (n?: number) => (n ?? 0).toLocaleString("vi-VN");
  return (
    <>
      <section className="hero">
        <div className="wrap hero-copy">
          <p className="eyebrow"><span className="pip" />Hriăm · tiếng Ê Đê nghĩa là <em>học</em></p>
          <h1 className="h-hero">Giữ tiếng Ê Đê sống trong từng câu nói hằng ngày</h1>
          <p className="lead">Dịch, tra từ, hỏi đáp và cùng nhau bổ sung ngữ liệu. Mọi dữ liệu chính thức đều có nguồn và được người bản ngữ xác minh.</p>
          <form className="quick" onSubmit={(e) => { e.preventDefault(); if (text.trim()) nav(`/translate?text=${encodeURIComponent(text.trim())}`); }}>
            <label className="sr-only" htmlFor="quick">Câu cần dịch</label>
            <input id="quick" value={text} onChange={(e) => setText(e.target.value)} placeholder="Nhập một câu tiếng Kinh hoặc tiếng Ê Đê…" />
            <button className="btn primary">Dịch</button>
          </form>
        </div>
        <div className="hem" aria-hidden />
      </section>
      <div className="wrap page">
        <div className="entries">
          {ENTRIES.map(([to, title, desc, motif]) => (
            <Link key={to} to={to} className="entry-card">
              <img src={`/brand/icon-${motif}.svg`} alt="" width="44" height="44" />
              <h2>{title}</h2><p>{desc}</p>
            </Link>
          ))}
        </div>
        <section className="about">
          <div>
            <p className="eyebrow light">Vòng tuần hoàn dữ liệu</p>
            <h2 className="big">Cộng đồng là chủ thể của ngôn ngữ</h2>
            <p>Bạn dùng và đóng góp; chuyên gia tiếng Ê Đê xác minh; dữ liệu đã duyệt quay lại làm từ điển và bản dịch tốt hơn.
              AI chỉ gợi ý, không tự công nhận nghĩa nào là chuẩn. <Link to="/about">Tìm hiểu thêm</Link></p>
          </div>
          <dl className="facts">
            <div><dt>{fmt(stats.data?.entries)}</dt><dd>mục từ</dd></div>
            <div><dt>{fmt(stats.data?.examples)}</dt><dd>câu ví dụ</dd></div>
            <div><dt>{fmt(stats.data?.verified_senses)}</dt><dd>nghĩa đã xác minh</dd></div>
          </dl>
        </section>
        <p className="center muted small mt"><Link to="/rules">Quy tắc cộng đồng</Link> · <Link to="/privacy">Quyền riêng tư</Link> · <Link to="/contribute">Đóng góp từ mới</Link></p>
      </div>
    </>
  );
}
