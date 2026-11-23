# Hriăm: nền tảng ngôn ngữ Ê Đê – tiếng Kinh

Đồ án môn Xử lý ngôn ngữ tự nhiên (NLP501): bộ dữ liệu song ngữ, mô hình dịch Ê Đê ↔ tiếng Kinh (tinh chỉnh NLLB-200)
và nền tảng web React + FastAPI làm theo bộ tài liệu phát triển (đối chiếu từng điểm: [docs/DOI_CHIEU_TAI_LIEU.md](docs/DOI_CHIEU_TAI_LIEU.md)).

## Cấu trúc

```text
frontend/            Giao diện React + TypeScript (Vite, React Router, TanStack Query, Zustand, React Hook Form + Zod)
  public/brand/      Logo, màu, hoa văn (sinh bằng scripts/make_brand.py)
backend/             API FastAPI + SQLAlchemy + Alembic (SQLite khi dev, PostgreSQL/Supabase khi deploy)
  app/api/v1/        auth, translation, forum, contributions, admin
  app/services/      pipeline dịch, từ điển, đóng góp, kiểm duyệt, strike, dataset release
  app/integrations/  adapter dịch máy (NLLB cục bộ, Gemini tuỳ chọn) và kiểm duyệt theo quy tắc
  app/tests/         42 test
  migrations/        Alembic
models/              Mô hình chính thức, không đưa lên git (chép tay sang máy host)
  ede2vi/, vi2ede/   File mô hình; eval/ chứa kết quả đánh giá
scripts/             Dữ liệu, train, dịch, chạy server
  bible_scraper.py, realign.py               Cào và căn câu Kinh Thánh
  parse_ac.py, validate_ac.py, build_ac.py, dict_xlsx.py, split_dict.py   Dựng từ điển
  build_dataset.py, build_daily.py           Dựng bộ dữ liệu (chung và văn nói)
  train.py, train_daily.py                   Train (cần card NVIDIA)
  translate.py                               Dịch bằng mô hình (backend dùng lại file này)
  serve_public.ps1, serve_public.bat         Bật backend + Cloudflare Tunnel một lệnh (Windows)
  make_brand.py                              Sinh bộ nhận diện
data/                raw/ (PDF, HTML đã cào, câu hội thoại), verified/, dictionary/, interim/, dataset/
docs/                HUONG_DAN.md, DEPLOY.md, BRAND.md, DOI_CHIEU_TAI_LIEU.md
  bao-cao/           Báo cáo, slide và kịch bản thuyết trình
runs/                Kết quả train tạm, không đưa lên git
```

## Chạy trên máy

```bash
conda activate msa
cd backend
pip install -r requirements.txt -r requirements-ml.txt
python -m app.cli setup                 # tạo bảng, vai trò, nguồn/giấy phép, nhập từ điển
python -m app.cli create-admin --username admin
uvicorn app.main:app --port 8000        # API: http://127.0.0.1:8000/api/v1/docs
python -m pytest app/tests              # chạy test

cd ../frontend
npm install
npm run dev                             # http://127.0.0.1:5173 (tự chuyển /api tới cổng 8000)
```

- Dịch máy dùng `models/ede2vi` và `models/vi2ede`; thiếu mô hình thì trả bản ghép nghĩa kèm nhãn "Cần xem lại".
- Câu khớp nguyên văn với ví dụ trong từ điển được trả luôn, nhãn "Ví dụ trong từ điển" (chưa chuyên gia xác minh).
- Gemini (tuỳ chọn): đặt `GEMINI_API_KEY` trong `backend/.env`. `MT_PROVIDER=local` chỉ dùng mô hình cục bộ; `auto` dùng mô hình cục bộ trước, thiếu hoặc lỗi thì Gemini; `gemini` dùng Gemini trước, lỗi thì rơi về mô hình cục bộ. Khi dùng Gemini, văn bản được gửi ra ngoài (Google) và giao diện ghi rõ điều này.
- Gán vai trò: `python -m app.cli grant --username lan --role language_expert`, hoặc trong Quản trị → Người dùng.

## Deploy

Vercel (giao diện) + backend và mô hình chạy trên máy một thành viên, mở ra Internet qua Cloudflare Tunnel + Supabase (database): [docs/DEPLOY.md](docs/DEPLOY.md).

## Train mô hình

```bash
conda activate msa
pip install -r requirements.txt
python scripts/train.py --check
python scripts/train_daily.py ede2vi   # train theo văn nói hằng ngày, hai giai đoạn, cần card NVIDIA
python scripts/translate.py "Jŭ msĕ si ak"
```

Train xong, chép `runs/<hướng>-noi/best/` vào `models/<hướng>/` để ứng dụng dùng.

`train_daily.py` train nền trên toàn bộ dữ liệu (Kinh Thánh dùng bản tiếng Việt hiện đại), rồi train tiếp trên câu đời thường để dịch tự nhiên hơn. Câu hội thoại do người bản ngữ dịch đặt trong `data/raw/hoi_thoai/`. Xem [docs/HUONG_DAN.md](docs/HUONG_DAN.md#train-theo-văn-nói-hằng-ngày).

Để dựng lại dữ liệu, xem [docs/HUONG_DAN.md](docs/HUONG_DAN.md).

## Dữ liệu

| Tập | Số cặp |
|---|---:|
| `train` | 35.367 |
| `dev_bible` / `dev_dict` | 793 / 182 |
| `test_bible` / `test_dict` | 665 / 297 |

Nguồn gồm Kinh Thánh hai bản, Từ điển Ê Đê – Việt (3.893 mục, 3.112 ví dụ) và vài câu ví dụ trong một bài báo về tách từ tiếng Ê Đê.

## Hạn chế và bản quyền

- Khoảng 80% tập train là văn Kinh Thánh, phần tiếng Việt là bản dịch năm 1925.
- Bản scan từ điển thiếu trang 146–147 của sách. Phần A–Č đã đối chiếu từng dòng với scan, phần D–Y mới đối chiếu một phần, và chưa có người bản ngữ rà soát.
- Bản Ê Đê 2015 nhiều khả năng còn bản quyền, nên repo này cần để private. Muốn công bố dữ liệu, cần xin phép bên giữ bản quyền.
- NLLB có giấy phép CC-BY-NC, chỉ dùng phi thương mại.
