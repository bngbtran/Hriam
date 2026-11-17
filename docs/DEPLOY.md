# Deploy Hriăm (miễn phí)

```text
Người dùng → Vercel (React, frontend/) ──/api──→ Hugging Face Space (FastAPI + NLLB, CPU) → Supabase (PostgreSQL)
                                   ↑
              UptimeRobot gọi /api/v1/health mỗi 5 phút: giữ Space thức và Supabase không bị tạm dừng
```

| Phần | Dịch vụ | Gói |
|---|---|---|
| Giao diện | Vercel | Hobby (miễn phí) |
| Backend + mô hình | Hugging Face Space, Docker | CPU Basic (2 vCPU, 16 GB RAM, miễn phí) |
| Mô hình | Hugging Face, repo mô hình riêng tư | Miễn phí |
| Database | Supabase | Free (500 MB) |
| Giữ thức | UptimeRobot | Free (5 phút một lần) |

Mọi lệnh chạy từ thư mục gốc repo, trong `conda activate msa`. Thay `ten-ban` bằng tên tài khoản Hugging Face của bạn.

## 1. Supabase

1. Tạo project mới trên supabase.com, đặt mật khẩu database (lưu lại). Region nên chọn gần Space (Hugging Face thường chạy ở Mỹ): East US.
   Vào **Project Settings → Data API**, tắt Data API: Hriăm kết nối thẳng PostgreSQL, không dùng API tự sinh của Supabase, tắt đi để không ai đọc được bảng qua khoá công khai.
2. Vào **Connect → Session pooler**, sao chép chuỗi kết nối. Đổi `postgresql://` thành `postgresql+psycopg://` và điền mật khẩu:
   `postgresql+psycopg://postgres.xxxx:MATKHAU@aws-0-xx.pooler.supabase.com:5432/postgres`
3. Tạo bảng và nhập từ điển **từ máy của bạn** (từ điển không đưa lên Space):

```bash
cd backend
pip install -r requirements.txt
DATABASE_URL="postgresql+psycopg://..." python -m app.cli setup
DATABASE_URL="postgresql+psycopg://..." python -m app.cli create-admin --username admin
```

> Từ điển scan chưa có giấy phép (docs/DOI_CHIEU_TAI_LIEU.md). Nếu web công khai, cân nhắc bỏ bước nhập từ điển: thay `setup` bằng `migrate` rồi `seed`.

## 2. Hugging Face

1. Tạo tài khoản, vào **Settings → Access Tokens** tạo token quyền **Write**, rồi đăng nhập trên máy: `hf auth login`.
2. Tải mô hình lên repo riêng tư (khoảng 4,6 GB):

```bash
python scripts/deploy_hf.py models --repo ten-ban/hriam-models
```

3. Tạo Space và tải backend lên:

```bash
python scripts/deploy_hf.py space --repo ten-ban/hriam-api
```

4. Trong Space, vào **Settings → Variables and secrets**:

| Loại | Tên | Giá trị |
|---|---|---|
| Secret | `DATABASE_URL` | Chuỗi Supabase ở bước 1 |
| Secret | `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| Secret | `PHONE_HMAC_KEY` | Tạo như trên, **khác** `SECRET_KEY`, không đổi về sau |
| Secret | `HF_TOKEN` | Token **Read** đọc được repo `hriam-models` |
| Variable | `HF_MODEL_REPO` | `ten-ban/hriam-models` |
| Variable | `CORS_ORIGINS` | `https://ten-du-an.vercel.app` |

5. Space tự build lại (khoảng 5–10 phút lần đầu). Mở `https://ten-ban-hriam-api.hf.space/api/v1/health`:
   `"database": "ok"` và `"translation": {"ede2vi": true, "vi2ede": true}` là xong. Mô hình tải ở nền, có thể mất 1–3 phút sau khi Space chạy; trong lúc đó dịch trả bản ghép nghĩa.

Cập nhật backend về sau: chạy lại lệnh ở bước 3. Cập nhật mô hình: chép mô hình mới vào `models/`, chạy lại bước 2, rồi **Factory rebuild** Space.

## 3. Vercel

1. Sửa `frontend/vercel.json`: thay `TEN-BAN-hriam-api` bằng địa chỉ Space thật (dạng `ten-ban-hriam-api`), commit và push.
2. Trên vercel.com: **Add New → Project**, chọn repo GitHub, đặt:
   - **Root Directory:** `frontend`
   - **Framework Preset:** Vite (tự nhận). Build `npm run build`, Output `dist`.
   - Không cần biến môi trường: mọi lời gọi `/api` đi qua Vercel tới Space, nên cookie đăng nhập dùng chung tên miền.
3. Deploy. Mở trang, thử dịch và đăng nhập bằng tài khoản admin đã tạo.

## 4. UptimeRobot

Tạo monitor **HTTP(s)**:

- URL: `https://ten-du-an.vercel.app/api/v1/health` (đi qua Vercel → Space → database, giữ cả ba hoạt động)
- Interval: 5 phút

`/api/v1/health` có truy vấn database thật, nên Supabase không bị tạm dừng vì "không hoạt động".

## Lưu ý

- **Giới hạn gói miễn phí** có thể thay đổi. Có báo cáo từ khoảng tháng 7/2026 rằng Hugging Face hạn chế Space Docker trên CPU Basic cho tài khoản miễn phí; nếu không tạo được Space, chuyển backend sang Oracle Cloud Always Free (cùng `Dockerfile`).
- **Tốc độ:** chạy CPU nên mỗi câu mất khoảng 1–3 giây (`MT_BEAMS=2`). Space khởi động lại thì mất 1–3 phút nạp lại mô hình.
- **Bảo mật:** không commit `backend/.env`. `PHONE_HMAC_KEY` đổi thì các hạn chế số điện thoại cũ mất tác dụng.
- **Bản quyền:** NLLB và mô hình tinh chỉnh dùng giấy phép CC-BY-NC (phi thương mại). Space công khai mã backend, không chứa dữ liệu.
