# Hriam: dịch máy Ê Đê – Việt

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
app/
  server.py          Web dịch Việt ↔ Ê Đê (python app/server.py)
  static/index.html  Giao diện web
docs/
  HUONG_DAN.md       Hướng dẫn chi tiết
data/
  raw/               PDF gốc, HTML đã cào, bản chép tay từ điển lần đầu
  verified/          Bản chép từ điển đã đối chiếu với scan (nguồn chính)
  dictionary/        Từ điển có cấu trúc: JSON, Excel, tách theo chữ cái
  interim/           Kinh Thánh đã cào và căn câu
  dataset/           Bộ dữ liệu cuối
runs/                Mô hình và kết quả, không đưa lên git
```

## Web dịch

```bash
conda activate msa
python app/server.py
```

Mở http://127.0.0.1:8000. Web chạy được ngay, không cần train:

- **Dịch từng từ:** ghép nghĩa theo từ điển, nhận cả chữ Ê Đê gõ thiếu dấu.
- **Câu song ngữ tương tự:** tìm trong khoảng 33.000 cặp câu Kinh Thánh và ví dụ từ điển.
- **Từ điển:** nghĩa và ví dụ của từng mục từ có trong câu.

Bản ghép từ chưa đúng ngữ pháp. Muốn dịch cả câu cần train mô hình như bên dưới; khi có `runs/<hướng>/best`, web tự hiện thêm bản dịch máy.

## Bắt đầu nhanh

```bash
conda activate msa
pip install -r requirements.txt
python scripts/train.py --check
caffeinate -i python scripts/train.py
python scripts/translate.py "Jŭ msĕ si ak"
```

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
