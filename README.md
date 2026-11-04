# Hriam: dịch máy Ê Đê – Việt

Đồ án môn Xử lý ngôn ngữ tự nhiên (NLP501): xây dựng bộ dữ liệu song ngữ và mô hình dịch Ê Đê – Việt bằng cách tinh chỉnh NLLB.

## Cấu trúc

```text
scripts/
  bible_scraper.py   Cào Kinh Thánh hai bản
  realign.py         Căn câu theo nội dung
  dict_parse.py      Phân tích bản chép tay từ điển
  build_dataset.py   Gộp nguồn, chia train/dev/test
  train.py           Train và đánh giá trên máy
docs/
  HUONG_DAN.md       Hướng dẫn chi tiết
data/
  raw/               PDF gốc, HTML đã cào, bản chép tay từ điển
  interim/           Dữ liệu trung gian
  dataset/           Bộ dữ liệu cuối
runs/                Mô hình và kết quả, không đưa lên git
```

## Bắt đầu nhanh

```bash
conda activate msa
pip install -r requirements.txt
python scripts/train.py --check
caffeinate -i python scripts/train.py
```

Để dựng lại dữ liệu, xem [docs/HUONG_DAN.md](docs/HUONG_DAN.md).

## Dữ liệu

| Tập | Số cặp |
|---|---:|
| `train` | 35.352 |
| `dev_bible` / `dev_dict` | 793 / 192 |
| `test_bible` / `test_dict` | 665 / 292 |

Nguồn gồm Kinh Thánh hai bản, Từ điển Ê Đê – Việt và vài câu ví dụ trong một bài báo về tách từ tiếng Ê Đê.

## Hạn chế và bản quyền

- Khoảng 80% tập train là văn Kinh Thánh, phần tiếng Việt là bản dịch năm 1925.
- Bản scan từ điển thiếu trang 146–147 của sách, và bản chép tay chưa được người bản ngữ rà soát.
- Bản Ê Đê 2015 nhiều khả năng còn bản quyền, nên repo này cần để private. Muốn công bố dữ liệu, cần xin phép bên giữ bản quyền.
- NLLB có giấy phép CC-BY-NC, chỉ dùng phi thương mại.
