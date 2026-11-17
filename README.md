# Hriăm: nền tảng ngôn ngữ Ê Đê – tiếng Kinh

Đồ án môn Xử lý ngôn ngữ tự nhiên (NLP501): xây dựng bộ dữ liệu song ngữ và mô hình dịch Ê Đê – Việt bằng cách tinh chỉnh NLLB.

## Cấu trúc

```text
scripts/
  bible_scraper.py   Cào Kinh Thánh hai bản
  realign.py         Căn câu theo nội dung
  parse_ac.py, validate_ac.py, build_ac.py, dict_xlsx.py, split_dict.py
                     Dựng từ điển từ bản chép đã đối chiếu (xem data/dictionary/README.md)
  build_dataset.py   Gộp nguồn, chia train/dev/test
  train.py           Train và đánh giá trên máy
  translate.py       Dịch bằng mô hình đã train
  export_web_data.py Xuất dữ liệu cho web
  make_brand.py      Sinh logo và hoa văn theo lối dệt thổ cẩm
backend/, frontend/  Nền tảng Hriăm (xem mục bên dưới)
web/                 Web tĩnh cũ (tham khảo)
docs/
  HUONG_DAN.md       Hướng dẫn chi tiết
  BRAND.md           Bộ nhận diện Hriăm: logo, màu, chữ, hoa văn
data/
  raw/               PDF gốc, HTML đã cào, bản chép tay từ điển lần đầu
  verified/          Bản chép từ điển đã đối chiếu với scan (nguồn chính)
  dictionary/        Từ điển có cấu trúc: JSON, Excel, tách theo chữ cái
  interim/           Kinh Thánh đã cào và căn câu
  dataset/           Bộ dữ liệu cuối
runs/                Mô hình và kết quả, không đưa lên git
```

## Nền tảng Hriăm (React + FastAPI)

Ứng dụng chính, làm theo bộ tài liệu phát triển (bản gốc lưu ngoài repo) (đối chiếu từng điểm: [docs/DOI_CHIEU_TAI_LIEU.md](docs/DOI_CHIEU_TAI_LIEU.md)).

```text
backend/    FastAPI + SQLAlchemy + Alembic (SQLite khi dev, PostgreSQL khi production)
  app/api/v1/        auth, translation, forum, contributions, admin
  app/services/      pipeline dịch, từ điển, đóng góp, kiểm duyệt, strike, dataset release
  app/integrations/  adapter dịch máy (NLLB) và kiểm duyệt theo quy tắc
  app/tests/         27 test theo docs/09
frontend/   React + TypeScript (Vite, React Router, TanStack Query, Zustand, React Hook Form + Zod)
```

Chạy trên máy (không cần Docker):

```bash
conda activate msa
cd backend
pip install -r requirements.txt
python -m app.cli setup                 # tạo bảng, vai trò, nguồn/giấy phép, nhập từ điển
python -m app.cli create-admin --username admin
uvicorn app.main:app --port 8000        # API: http://127.0.0.1:8000/api/v1/docs
python -m pytest app/tests              # chạy test

cd ../frontend
npm install
npm run dev                             # http://127.0.0.1:5173 (tự chuyển /api tới cổng 8000)
```

Gán vai trò: `python -m app.cli grant --username lan --role language_expert` (hoặc trong trang Quản trị → Người dùng).
Dịch máy dùng mô hình trong `runs/` nếu có; không có thì trả bản ghép nghĩa kèm nhãn "Cần xem lại".

Deploy: `frontend/` lên Vercel (Framework: Vite, build `npm run build`, output `dist`); sửa `frontend/vercel.json` để `/api` trỏ tới máy chủ chạy backend.
Backend cần một máy chủ Python (có GPU/CPU cho mô hình) và PostgreSQL; đặt biến môi trường theo `backend/.env.example`.

Web tĩnh cũ (`web/`, `scripts/serve_model.py`) vẫn còn để tham khảo, không còn là ứng dụng chính.

## Bắt đầu nhanh

```bash
conda activate msa
pip install -r requirements.txt
python scripts/train.py --check
python scripts/train_daily.py ede2vi   # train theo văn nói hằng ngày, hai giai đoạn, cần card NVIDIA
python scripts/translate.py "Jŭ msĕ si ak"
```

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
