"""RBAC (docs/01 §3, docs/02 §8, docs/07). Quyền kiểm tra ở backend; giao diện chỉ ẩn/hiện cho tiện."""
from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    "forum.post": "Đăng bài, bình luận, báo cáo nội dung",
    "contribution.submit": "Gửi đóng góp từ/câu/cụm",
    "translation.feedback": "Báo lỗi và đề xuất bản dịch",
    "appeal.submit": "Gửi khiếu nại",
    "lexicon.review": "Xem hàng chờ đóng góp",
    "lexicon.approve": "Duyệt đóng góp vào Master Lexicon",
    "lexicon.reject": "Từ chối đóng góp",
    "lexicon.verify": "Xác minh nghĩa ở mức chuyên gia ngôn ngữ",
    "lexicon.candidate_review": "Xem ứng viên từ/nghĩa do AI phát hiện",
    "dataset.read": "Xem dataset release",
    "dataset.release": "Tạo dataset release",
    "moderation.review": "Xem hàng chờ kiểm duyệt",
    "moderation.decide": "Quyết định đăng/từ chối/gỡ nội dung",
    "moderation.annotate": "Ghi chú ngôn ngữ/ngữ cảnh cho case kiểm duyệt",
    "user.strike": "Áp dụng strike",
    "appeal.review": "Xem khiếu nại",
    "appeal.decide": "Quyết định khiếu nại",
    "user.read": "Xem danh sách người dùng",
    "user.ban": "Khoá tài khoản",
    "user.unban": "Mở khoá tài khoản",
    "user.roles": "Gán vai trò",
    "audit.read": "Xem nhật ký kiểm toán",
    "phone_restriction.manage": "Quản lý hạn chế số điện thoại",
    "settings.manage": "Quản lý cấu hình, chuẩn chữ viết",
    "culture.read": "Xem tư liệu văn hoá theo cấp quyền",
    "culture.submit": "Đóng góp tư liệu văn hoá",
    "culture.review": "Duyệt tư liệu văn hoá",
    "culture.restricted": "Truy cập tư liệu văn hoá hạn chế",
    "conversation.manage": "Quản lý phòng hội thoại",
}

_USER = ["forum.post", "contribution.submit", "translation.feedback", "appeal.submit", "culture.read", "culture.submit"]

# Admin không mặc nhiên là Language Expert: không có lexicon.verify (docs/01 §3).
ROLES: dict[str, tuple[str, list[str]]] = {
    "user": ("Thành viên", _USER),
    "trusted_contributor": ("Người đóng góp tin cậy", _USER + ["lexicon.review"]),
    "language_expert": ("Chuyên gia ngôn ngữ", _USER + [
        "lexicon.review", "lexicon.approve", "lexicon.reject", "lexicon.verify", "lexicon.candidate_review",
        "dataset.read", "moderation.annotate", "culture.review", "culture.restricted"]),
    "moderator": ("Người kiểm duyệt", _USER + [
        "moderation.review", "moderation.decide", "user.strike", "appeal.review", "appeal.decide", "user.read"]),
    "admin": ("Quản trị viên", [p for p in PERMISSIONS if p not in ("lexicon.verify", "moderation.annotate")]),
}
