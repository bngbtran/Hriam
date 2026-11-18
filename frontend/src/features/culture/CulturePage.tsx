import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { EdeKeyboard } from "../../components/EdeKeyboard";
import { Badge, Empty, ErrorBox, PageHead, Spinner, fmtDate } from "../../components/ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { CulturalItem } from "../../lib/types";

const CATEGORIES = [
  { id: "", label: "Tất cả danh mục" },
  { id: "story", label: "Truyện kể dân gian" },
  { id: "song", label: "Lời hát / dân ca" },
  { id: "proverb_idiom", label: "Tục ngữ / thành ngữ" },
  { id: "history", label: "Tư liệu lịch sử" },
  { id: "custom", label: "Phong tục / nghi lễ" },
  { id: "term", label: "Thuật ngữ văn hoá" },
];

const TIERS = [
  { id: "", label: "Tất cả cấp quyền" },
  { id: "public", label: "Công khai (Public)" },
  { id: "community", label: "Cộng đồng (Community)" },
  { id: "restricted", label: "Hạn chế (Restricted)" },
  { id: "private", label: "Riêng tư (Private)" },
];

const TIER_DESCRIPTIONS: Record<string, string> = {
  public: "Ai cũng có thể xem tự do khi người kể và người đóng góp đồng ý.",
  community: "Chỉ thành viên cộng đồng đã đăng nhập tài khoản Hriam.",
  restricted: "Tư liệu nghi lễ, phong tục thiêng hoặc yêu cầu xem xét cẩn trọng.",
  private: "Lưu trữ bản nháp của cá nhân, chưa công bố ra bên ngoài.",
};

export function CulturePage() {
  const { user, can } = useAuth();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [tier, setTier] = useState("");
  const [selectedItem, setSelectedItem] = useState<CulturalItem | null>(null);
  const [showSubmitModal, setShowSubmitModal] = useState(false);

  const edeInputRef = useRef<HTMLTextAreaElement>(null);
  const [formCategory, setFormCategory] = useState("story");
  const [formTitle, setFormTitle] = useState("");
  const [formContentEde, setFormContentEde] = useState("");
  const [formContentVi, setFormContentVi] = useState("");
  const [formSummary, setFormSummary] = useState("");
  const [formStoryteller, setFormStoryteller] = useState("");
  const [formRegion, setFormRegion] = useState("");
  const [formTier, setFormTier] = useState<"public" | "community" | "restricted" | "private">("public");
  const [consentDisplay, setConsentDisplay] = useState(true);
  const [consentResearch, setConsentResearch] = useState(true);
  const [reviewNote, setReviewNote] = useState("");

  const itemsQuery = useQuery({
    queryKey: ["culture-items", category, tier, q],
    queryFn: () =>
      api.page<CulturalItem[]>("/culture/items", {
        category: category || undefined,
        access_tier: tier || undefined,
        q: q.trim() || undefined,
      }),
  });

  const detailQuery = useQuery({
    queryKey: ["culture-item", selectedItem?.id],
    queryFn: () => api.get<CulturalItem>(`/culture/items/${selectedItem?.id}`),
    enabled: !!selectedItem?.id,
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      api.post<CulturalItem>("/culture/items", {
        category: formCategory,
        title: formTitle.trim(),
        content_ede: formContentEde.trim(),
        content_vi: formContentVi.trim(),
        summary: formSummary.trim() || null,
        storyteller_or_author: formStoryteller.trim() || null,
        region: formRegion.trim() || null,
        access_tier: formTier,
        consent_flags: {
          public_display: consentDisplay,
          research_analysis: consentResearch,
        },
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["culture-items"] });
      setShowSubmitModal(false);
      setFormTitle("");
      setFormContentEde("");
      setFormContentVi("");
      setFormSummary("");
      setFormStoryteller("");
      setFormRegion("");
    },
  });

  const reviewMutation = useMutation({
    mutationFn: ({ approve }: { approve: boolean }) =>
      api.post(`/culture/items/${selectedItem?.id}/review`, {
        approve,
        decision_note: reviewNote.trim() || (approve ? "Duyệt xuất bản." : "Từ chối."),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["culture-items"] });
      qc.invalidateQueries({ queryKey: ["culture-item", selectedItem?.id] });
      setReviewNote("");
    },
  });

  const activeItem = detailQuery.data ?? selectedItem;

  return (
    <div className="wrap page">
      <PageHead eyebrow="Văn hoá" title="Kho tư liệu văn hoá Ê Đê">
        Lưu trữ truyện kể, lời ca điệu hát, tục ngữ và phong tục tập quán Ê Đê theo 4 cấp quyền truy cập,
        tôn trọng quyền tự quyết của người kể chuyện và các buôn làng (docs/01 §4.10, docs/08 §7-8).
      </PageHead>

      {/* 4 Cấp quyền truy cập */}
      <div className="principles">
        {Object.entries(TIER_DESCRIPTIONS).map(([k, desc], idx) => (
          <div key={k} className="principle">
            <span className="num">{idx + 1}</span>
            <h3>{TIERS.find((t) => t.id === k)?.label.replace(/\s*\(.*\)$/, "")}</h3>
            <p>{desc}</p>
          </div>
        ))}
      </div>

      {/* Thanh tìm kiếm & lọc */}
      <div className="card mt mb">
        <div className="row wrap-row">
          <input
            type="search"
            placeholder="Tìm theo tiêu đề, người kể, địa phương…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            style={{ flex: 1, minWidth: "220px" }}
          />
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
          <select value={tier} onChange={(e) => setTier(e.target.value)}>
            {TIERS.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
          </select>
          {user ? (
            <button className="btn primary" onClick={() => setShowSubmitModal(true)}>
              + Đóng góp tư liệu
            </button>
          ) : (
            <Link className="btn ghost" to="/login?next=/culture">
              Đăng nhập để đóng góp
            </Link>
          )}
        </div>
      </div>

      {/* Danh sách tư liệu */}
      {itemsQuery.isLoading ? (
        <Spinner label="Đang tải kho tư liệu văn hoá…" />
      ) : itemsQuery.error ? (
        <ErrorBox error={itemsQuery.error} />
      ) : !itemsQuery.data?.data.length ? (
        <Empty motif="qua-tram">
          <p>Không tìm thấy tư liệu nào phù hợp với bộ lọc hiện tại.</p>
        </Empty>
      ) : (
        <div className="grid two-col" style={{ gap: "1rem" }}>
          {itemsQuery.data.data.map((item) => (
            <div
              key={item.id}
              className="card clickable hover-card"
              style={{ cursor: "pointer", display: "flex", flexDirection: "column", justifyContent: "space-between" }}
              onClick={() => setSelectedItem(item)}
            >
              <div>
                <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                  <span className="badge muted">{item.category_label}</span>
                  <span className={`badge ${item.access_tier === "public" ? "ok" : item.access_tier === "community" ? "info" : "warn"}`}>
                    {item.access_tier.toUpperCase()}
                  </span>
                </div>
                <h3 style={{ margin: "0.25rem 0" }}>{item.title}</h3>
                {item.summary && <p className="muted small" style={{ margin: "0.5rem 0" }}>{item.summary}</p>}
              </div>
              <div className="row small muted" style={{ justifyContent: "space-between", marginTop: "1rem", borderTop: "1px solid var(--border)", paddingTop: "0.5rem" }}>
                <span>{item.storyteller_or_author ? `Người kể: ${item.storyteller_or_author}` : "Khuyết danh"}</span>
                <span>{item.region || fmtDate(item.created_at)}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal Chi tiết Tư liệu / Song ngữ */}
      {selectedItem && (
        <div className="modal-backdrop" onClick={() => setSelectedItem(null)}>
          <div className="modal card" style={{ maxWidth: "800px", width: "95%", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
              <span className="badge muted">{activeItem?.category_label}</span>
              <button className="btn ghost small" onClick={() => setSelectedItem(null)}>✕ Đóng</button>
            </div>
            <h2>{activeItem?.title}</h2>
            <div className="row small muted" style={{ gap: "1rem", marginBottom: "1rem" }}>
              {activeItem?.storyteller_or_author && <span><b>Người kể:</b> {activeItem.storyteller_or_author}</span>}
              {activeItem?.region && <span><b>Địa phương:</b> {activeItem.region}</span>}
              <span><b>Cấp quyền:</b> <Badge status={activeItem?.access_tier ?? "public"} /></span>
              <span><b>Trạng thái:</b> <Badge status={activeItem?.status ?? "published"} /></span>
            </div>

            {activeItem?.summary && (
              <div className="alert info" style={{ marginBottom: "1rem" }}>
                <b>Tóm tắt / Ý nghĩa:</b> {activeItem.summary}
              </div>
            )}

            {detailQuery.isLoading ? (
              <Spinner label="Đang tải nội dung văn bản…" />
            ) : activeItem?.content_ede || activeItem?.content_vi ? (
              <div className="two-col" style={{ gap: "1.5rem", marginTop: "1rem" }}>
                <div>
                  <h4 style={{ color: "var(--primary)" }}>Tiếng Ê Đê (Kleĉ Êđê)</h4>
                  <div
                    className="box"
                    style={{ background: "var(--surface-sunken)", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap", lineHeight: "1.6" }}
                    lang="rad"
                  >
                    {activeItem.content_ede || "Chưa có văn bản tiếng Ê Đê."}
                  </div>
                </div>
                <div>
                  <h4 style={{ color: "var(--primary)" }}>Bản dịch tiếng Kinh</h4>
                  <div
                    className="box"
                    style={{ background: "var(--surface-sunken)", padding: "1rem", borderRadius: "8px", whiteSpace: "pre-wrap", lineHeight: "1.6" }}
                  >
                    {activeItem.content_vi || "Chưa có bản dịch tiếng Kinh."}
                  </div>
                </div>
              </div>
            ) : (
              <div className="alert warning mt">
                🔒 Nội dung văn bản thuộc cấp quyền <b>{activeItem?.access_tier}</b>. Bạn cần đăng nhập hoặc có quyền truy cập được cấp phép để xem toàn văn tư liệu này.
              </div>
            )}

            {/* Moderator / Admin Review Actions */}
            {can("culture.review") && activeItem?.status === "pending_review" && (
              <div className="card mt" style={{ background: "var(--surface-sunken)" }}>
                <h4>Kiểm duyệt tư liệu này</h4>
                <textarea
                  rows={2}
                  placeholder="Ghi chú thẩm định hoặc lý do..."
                  value={reviewNote}
                  onChange={(e) => setReviewNote(e.target.value)}
                />
                <div className="row mt">
                  <button
                    className="btn primary"
                    onClick={() => reviewMutation.mutate({ approve: true })}
                    disabled={reviewMutation.isPending}
                  >
                    Phê duyệt xuất bản
                  </button>
                  <button
                    className="btn danger"
                    onClick={() => reviewMutation.mutate({ approve: false })}
                    disabled={reviewMutation.isPending}
                  >
                    Từ chối
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Modal Đóng góp tư liệu mới */}
      {showSubmitModal && (
        <div className="modal-backdrop" onClick={() => setShowSubmitModal(false)}>
          <div className="modal card" style={{ maxWidth: "700px", width: "95%", maxHeight: "90vh", overflowY: "auto" }} onClick={(e) => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2>Đóng góp tư liệu văn hoá mới</h2>
              <button className="btn ghost small" onClick={() => setShowSubmitModal(false)}>✕</button>
            </div>
            <p className="muted small">
              Tư liệu đóng góp sẽ được lưu trữ cùng thông tin người kể, địa phương và mức bảo vệ bạn lựa chọn.
            </p>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                submitMutation.mutate();
              }}
              className="form"
            >
              <div className="two-col">
                <div>
                  <label htmlFor="c_cat">Phân loại *</label>
                  <select id="c_cat" value={formCategory} onChange={(e) => setFormCategory(e.target.value)} required>
                    {CATEGORIES.filter((c) => c.id).map((c) => (
                      <option key={c.id} value={c.id}>{c.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label htmlFor="c_tier">Cấp quyền truy cập *</label>
                  <select id="c_tier" value={formTier} onChange={(e) => setFormTier(e.target.value as any)} required>
                    <option value="public">Công khai (Public) - Ai cũng xem được</option>
                    <option value="community">Cộng đồng (Community) - Cần đăng nhập</option>
                    <option value="restricted">Hạn chế (Restricted) - Nghi lễ / thiêng</option>
                    <option value="private">Riêng tư (Private) - Chỉ lưu nháp</option>
                  </select>
                </div>
              </div>

              <label htmlFor="c_title">Tiêu đề tư liệu *</label>
              <input
                id="c_title"
                type="text"
                placeholder="Ví dụ: Lời khuyên con cháu khi làm rẫy, Bài ca mừng lúa mới…"
                value={formTitle}
                onChange={(e) => setFormTitle(e.target.value)}
                required
              />

              <div className="two-col">
                <div>
                  <label htmlFor="c_author">Người kể / Nghệ nhân / Tác giả</label>
                  <input
                    id="c_author"
                    type="text"
                    placeholder="Tên nghệ nhân, già làng hoặc người kể"
                    value={formStoryteller}
                    onChange={(e) => setFormStoryteller(e.target.value)}
                  />
                </div>
                <div>
                  <label htmlFor="c_region">Buôn làng / Địa phương</label>
                  <input
                    id="c_region"
                    type="text"
                    placeholder="Ví dụ: Buôn Kmrơng Prông, Đắk Lắk"
                    value={formRegion}
                    onChange={(e) => setFormRegion(e.target.value)}
                  />
                </div>
              </div>

              <label htmlFor="c_summary">Tóm tắt / Bối cảnh diễn xướng</label>
              <textarea
                id="c_summary"
                rows={2}
                placeholder="Mô tả hoàn cảnh diễn xướng, ý nghĩa văn hoá hoặc bối cảnh…"
                value={formSummary}
                onChange={(e) => setFormSummary(e.target.value)}
              />

              <label htmlFor="c_ede">Nội dung tiếng Ê Đê *</label>
              <textarea
                id="c_ede"
                ref={edeInputRef}
                rows={4}
                placeholder="Nhập lời kể hoặc bài hát tiếng Ê Đê…"
                value={formContentEde}
                onChange={(e) => setFormContentEde(e.target.value)}
                required
              />
              <EdeKeyboard target={edeInputRef} onChange={setFormContentEde} compact />

              <label htmlFor="c_vi">Nội dung dịch / diễn giải tiếng Kinh *</label>
              <textarea
                id="c_vi"
                rows={4}
                placeholder="Bản dịch tiếng Kinh hoặc giải thích nghĩa chi tiết…"
                value={formContentVi}
                onChange={(e) => setFormContentVi(e.target.value)}
                required
              />

              <div className="mt">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={consentDisplay}
                    onChange={(e) => setConsentDisplay(e.target.checked)}
                  />
                  Tôi đồng ý cho hiển thị tư liệu này theo cấp quyền đã chọn.
                </label>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={consentResearch}
                    onChange={(e) => setConsentResearch(e.target.checked)}
                  />
                  Tôi đồng ý cho dự án Hriam sử dụng tư liệu cho mục đích nghiên cứu ngôn ngữ học và đào tạo AI bảo tồn.
                </label>
              </div>

              <ErrorBox error={submitMutation.error} />

              <div className="row mt" style={{ justifyContent: "flex-end" }}>
                <button type="button" className="btn ghost" onClick={() => setShowSubmitModal(false)}>
                  Huỷ
                </button>
                <button
                  type="submit"
                  className="btn primary"
                  disabled={submitMutation.isPending || !formTitle.trim() || !formContentEde.trim() || !formContentVi.trim()}
                >
                  {submitMutation.isPending ? "Đang gửi…" : "Gửi tư liệu"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
