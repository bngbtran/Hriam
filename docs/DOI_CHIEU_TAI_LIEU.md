# Đối chiếu với bộ tài liệu phát triển

So sánh ứng dụng hiện tại (`backend/`, `frontend/`) với bộ tài liệu phát triển (README và docs/01–11, bản gốc lưu ngoài repo). Mức độ:
**Đúng** (làm theo tài liệu), **Một phần** (mới làm một phần), **Chưa làm** (thuộc giai đoạn sau), **Khác** (cố ý làm khác, có lý do).

## Quyết định đã chốt với chủ dự án

| Điểm | Tài liệu | Ứng dụng | Mức độ |
|---|---|---|---|
| Phạm vi | MVP (docs/09 §3) | MVP: dịch, từ điển, diễn đàn có kiểm duyệt, đóng góp + duyệt, RBAC, audit | Đúng |
| Frontend | React + TypeScript, Vite, Router, TanStack Query, Zustand, RHF + Zod | Đúng các thư viện này, khoá phiên bản bằng `package-lock.json` | Đúng |
| Backend | FastAPI, Pydantic, SQLAlchemy 2, Alembic | Đúng | Đúng |
| Database | PostgreSQL | SQLite khi dev; đổi sang PostgreSQL bằng `DATABASE_URL` (code không dùng tính năng riêng của SQLite) | Khác |
| Docker Compose cho dev | Có | Không dùng Docker (theo yêu cầu) | Khác |
| Redis, hàng đợi việc nền | Redis + Celery/RQ | Không có. Rate limit lưu trong bộ nhớ, kiểm duyệt chạy ngay trong request | Khác |
| Object storage (S3) | Có | Chưa cần (chưa nhận upload ảnh/âm thanh); manifest dataset lưu ở `backend/storage/` | Khác |
| Tên gọi | "Ede Language & Culture Platform", "tiếng Kinh" | "Hriăm" + "tiếng Kinh" | Khác (giữ thương hiệu) |
| Nhãn bản dịch AI | Phân biệt rõ bản đã xác minh / bản AI | Nhãn ngắn: "Bản nháp máy dịch", "Đã xác minh", "Chuyên gia xác minh", "Cần xem lại" + cảnh báo từ chưa có/chưa xác minh | Đúng |

## docs/01 — Yêu cầu sản phẩm

| Mục | Mức độ | Ghi chú |
|---|---|---|
| 4.1 Trang chủ, lối vào nhanh, liên kết quy tắc/quyền riêng tư | Đúng | Chưa có "hoạt động nổi bật" (cần consent hiển thị công khai) |
| 4.2 Dịch hai chiều, chọn hướng, tra dữ liệu xác minh trước, trạng thái, sao chép, chia sẻ, lịch sử theo cài đặt, báo lỗi + đề xuất | Đúng | Phát âm/TTS chưa có (không có bản ghi/TTS đạt chuẩn) |
| 4.2 Nhận diện ngôn ngữ đầu vào | Một phần | API có `source_language: "auto"` (dựa vào ký tự riêng chữ Ê Đê); giao diện để người dùng chọn chiều |
| 4.3 Từ điển: nhiều nghĩa, biến thể, ví dụ, nguồn, giấy phép, trạng thái | Đúng | Chưa có phương ngữ, IPA, âm thanh, người xác minh hiển thị (chưa có dữ liệu) |
| 4.4 Diễn đàn: danh mục, đăng/bình luận, báo cáo, trạng thái bài, kiểm duyệt trước khi đăng | Đúng | Chưa đính kèm ảnh/video; chưa tạo đề xuất từ ngay trong bài |
| 4.5 Contribution Center | Đúng | Đóng góp âm thanh chưa mở |
| 4.6 Admin: hàng chờ, chi tiết, đã duyệt, dataset release, log từ chối | Đúng | Approve/reject có idempotency, audit, purge nội dung |
| 4.7 Automatic Lexical Discovery | Chưa làm | Giai đoạn 5 của lộ trình; có màn hình giữ chỗ và endpoint trả rỗng |
| 4.8 Kiểm duyệt, strike, khiếu nại, khoá, hạn chế số điện thoại | Đúng | Chưa kiểm duyệt ảnh/video (chưa có upload) |
| 4.9 Live Conversation | Một phần | Có chế độ một thiết bị, theo lượt, nhập bằng chữ; chưa có ASR, Push-to-Talk bằng giọng nói, VAD, phòng hai thiết bị, WebSocket |
| 4.10 Kho văn hoá | Chưa làm | Giai đoạn 8; có trang mô tả các mức quyền truy cập |
| 6 Strike thứ 4 khoá tài khoản, appeal huỷ strike, HMAC số điện thoại | Đúng | |
| 7 Phân trang, responsive, Unicode, accessibility, RBAC, audit | Đúng | Backup/restore và giám sát lỗi thuộc vận hành, chưa cấu hình |

## docs/02 — Kiến trúc

| Mục | Mức độ | Ghi chú |
|---|---|---|
| Modular monolith, router → service → model | Đúng | Phần repository gộp vào service (truy vấn SQLAlchemy trực tiếp) |
| Route frontend §2.2 | Đúng | Có thêm `/login`, `/register`, `/about`, `/rules`, `/privacy` |
| Adapter AI công bố ngôn ngữ, phiên bản, giấy phép, dữ liệu gửi ra ngoài, chỉ số | Đúng | `GET /translations/capabilities` |
| Worker idempotent | Một phần | Không có worker; các thao tác duyệt dùng Idempotency-Key và chống strike trùng |
| Realtime/WebRTC | Chưa làm | Đi cùng Live Conversation |
| Observability (tracing, metrics) | Một phần | Có request id và log; chưa có OpenTelemetry/metrics |

## docs/03 — Cơ sở dữ liệu

| Mục | Mức độ | Ghi chú |
|---|---|---|
| users, roles, permissions, user_roles, user_phone_restrictions | Đúng | Không lưu `phone_encrypted` (không có nhu cầu nghiệp vụ, chỉ giữ HMAC) |
| lexical_entries/forms/senses, corpus_examples, phrase_components, sources, licenses, translation_corpus | Đúng | |
| dataset_releases(+items) bất biến, có checksum | Đúng | Release có nguồn chưa duyệt giấy phép được đánh dấu "research_only" |
| contribution_submissions + purge khi reject | Đúng | |
| forum_posts/comments, moderation_cases/actions, user_strike_events, user_appeals, admin_audit_logs | Đúng | Thêm `content_reports`, `notifications`, `refresh_sessions`, `idempotency_keys`, `translation_history`, `translation_feedback` |
| lexical_candidates và các bảng AI | Chưa làm | Giai đoạn 5 |
| conversation_rooms/participants/turns | Chưa làm | Chế độ một thiết bị không lưu gì nên chưa cần |
| orthography_profiles, dialects | Đúng | Profile "ede-tudien-baseline" ở trạng thái nháp, chờ chuyên gia |

## docs/04 — Dữ liệu và AI

| Mục | Mức độ | Ghi chú |
|---|---|---|
| Unicode NFC, khoá tìm kiếm riêng, giữ dấu phụ | Đúng | Có test |
| Bàn phím ký tự theo profile, chèn tại con trỏ | Đúng | |
| Pipeline dịch 8 bước | Đúng | Tra mục từ đã xác minh → translation memory đã duyệt → mô hình → liệt kê thuật ngữ, cảnh báo từ lạ |
| Nhập nguồn có kiểm tra giấy phép | **Khác** | Từ điển scan được nhập vào Master Lexicon dù giấy phép đang "pending", nghĩa để "Chưa xác minh". Tài liệu yêu cầu không đưa vào production trước khi xin phép |
| Mô hình dịch train trên nguồn đã duyệt quyền | **Khác** | Mô hình hiện tại train trên từ điển scan và Kinh Thánh RRB/BPT, chưa có giấy phép. Chỉ dùng nghiên cứu |
| NIRVLab/rhade-vietnamese-mt | Chưa làm | Đã ghi vào nguồn/giấy phép (CC BY-NC), chưa nhập |
| ASR, TTS | Chưa làm | |

## docs/05–08 — Kiểm duyệt, hội thoại, API, bảo mật

| Mục | Mức độ | Ghi chú |
|---|---|---|
| Kiểm duyệt trước khi đăng; tiếng Ê Đê/không rõ → người duyệt | Đúng | Bộ lọc theo quy tắc (`rules-v1`), chưa có mô hình kiểm duyệt |
| Không tính strike từ quyết định tự động | Đúng | Spam rõ bị từ chối tự động nhưng không tính strike |
| Khiếu nại do người khác người quyết định ban đầu | Đúng | Áp dụng khi có từ 2 người kiểm duyệt trở lên |
| API `/api/v1`, `{data, meta}` / `{error}`, cursor, Idempotency-Key, mã lỗi | Đúng | OpenAPI tại `/api/v1/docs` |
| `POST /auth/verify-phone` | Chưa làm | Trả 501; cần nhà cung cấp SMS |
| Argon2id, access token ngắn, refresh xoay vòng + thu hồi khi dùng lại | Đúng | Refresh token ở cookie HttpOnly SameSite=Strict |
| MFA cho admin | Chưa làm | |
| Upload, quét malware, signed URL | Chưa làm | Chưa có upload |
| Consent tách mục đích | Đúng | Công bố / nghiên cứu / huấn luyện tách riêng; bài viết có consent phân tích riêng |

## docs/09 — Kiểm thử

27 test tự động (`backend/app/tests`): Unicode, quyền, approve một lần, reject purge + audit tối thiểu, bài chưa duyệt không công khai,
strike thứ 4 khoá + chặn số điện thoại, appeal giảm strike đúng một lần, admin mở khoá có audit, refresh xoay vòng, translation memory ưu tiên,
lịch sử chỉ lưu khi bật, dataset release có checksum. Chưa có: test frontend, test bảo mật OWASP, đánh giá bởi người bản ngữ.

## Việc cần chủ dự án quyết định (docs/10 §2)

1. Chuẩn chữ viết: profile nháp hiện lấy từ bảng chữ của từ điển scan; cần chuyên gia xác nhận (vd. `ŏ` hay `ơ̆`, mô hình đang viết lẫn hai kiểu).
2. Giấy phép: xin phép từ điển Êđê–Việt và Kinh Thánh, hoặc thay bằng nguồn được phép trước khi công khai.
3. Người có quyền xác minh (Language Expert) và người kiểm duyệt.
4. Thời hạn giữ hạn chế số điện thoại, bài bị từ chối.
5. Lộ trình cho Lexical Discovery, ASR/hội thoại giọng nói, kho văn hoá.
