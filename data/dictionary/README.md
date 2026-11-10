# Từ điển Êđê – Việt (A → Y)

Nguồn: `data/PDF/TuDienEDe.pdf` (bản scan; trang sách = trang PDF − 2). 3.893 mục, 3.112 cặp ví dụ.

## Tệp và thư mục

- `dictionary_full.xlsx` / `dictionary_full.json`: toàn bộ. Excel có sheet gộp A–Y, "Thống kê theo chữ", một sheet riêng cho từng chữ cái, Từng nghĩa, Ví dụ (song ngữ), Chữ viết tắt, Bảng chữ cái, Sửa lỗi OCR, Ghi chú nguồn.
- Các folder `01_…` đến `08_…`: mỗi folder 5 chữ cái liên tiếp theo bảng chữ cái Êđê, gồm `dictionary_NN.xlsx` và `dictionary_NN.json`.
- `reference/`: `abbreviations.json` và `alphabet.json`, chép từ các trang đầu của sách (dữ liệu gốc, không tái tạo được từ script).
- `_build/`: file trung gian của quá trình dựng (`_parsed.json`, `validation_report.json`, `corrections.json`…). Tái tạo được, có thể xóa.

| Folder | Mục |
|---|---|
| `01_A-Ă-Â-B-Ƀ` | 414 (Â không có mục nào) |
| `02_Č-D-Đ-E-Ĕ` | 389 |
| `03_Ê-Ê̆-G-H-I` | 635 |
| `04_Ĭ-J-K-L-M` | 1.191 |
| `05_N-Ñ-O-Ŏ-Ô` | 127 |
| `06_Ô̆-Ơ-Ơ̆-P-R` | 391 |
| `07_S-T-U-Ŭ-Ư` | 489 |
| `08_Ư̆-W-Y` | 257 |

Các mục dạng "Dh…", "Kh…", "Mđ…" nằm chung với chữ cái đầu của chúng (D, K, M). Bảng chữ cái Êđê không có chữ `C` riêng (âm "ch" viết là `Č`).

## Độ tin cậy

- **A–Č** (id `AC…`, trang PDF 7–26): đã đối chiếu từng dòng với ảnh scan (phóng 3,4× và 9–16× ở chỗ khó). Bản chép đã đối chiếu: `data/verified/AC/`.
- **D–Y** (id `DY…`, trang PDF 27–168): sửa lỗi hệ thống `ŏ` bị chép thành `ơ̆` (606 chỗ, xác nhận bằng ảnh phóng lớn). Đối chiếu từng chữ toàn trang ở trang PDF 27–31, 59, 75, 110, 140, 152; một phần ở trang 34, 82, 107, 121. Khoảng 125 trang còn lại chỉ quét tự động. Bản chép: `data/verified/DY/`. Mục "Ơ̆" (trang 121) có râu thật nên giữ nguyên.
- Chưa có người bản ngữ rà soát. Dấu phụ dễ nhầm: `ŏ`/`ơ̆`/`ô̆`, `ĕ`/`ê̆`, `ư̆`/`ŭ`.
- Giữ nguyên chính tả của sách (`ê̆`, `ô̆`, `ư̆`… khác Kinh Thánh Êđê 2015; hai nguồn không cùng quy ước).
- Nhãn từ loại in lạ (`ct`, `ht`, `bt`, `pt`, `đt` trên nghĩa danh từ) và lỗi in tiếng Việt ("Aó", "Qủa", "qúy") được giữ nguyên và ghi trong cột "Ghi chú" / trường `notes`.

## Dựng lại

```
set DICT_TAG=AC           (PowerShell: $env:DICT_TAG='AC'; sau đó làm lại với 'DY')
python -I scripts/parse_ac.py
python -I scripts/validate_ac.py
python scripts/build_ac.py        # không dùng -I (cần openpyxl)
python scripts/split_dict.py      # chạy sau khi đã làm cả AC và DY
```
