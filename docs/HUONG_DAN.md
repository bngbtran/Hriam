# Hướng dẫn

Mọi lệnh chạy từ thư mục gốc của repo, trong môi trường conda `msa`:

```bash
cd ~/BNGBTRAN/NLP501/PROJECT/Hriam
conda activate msa
pip install -r requirements.txt
```

> zsh trên Mac không hiểu chú thích `# ...` đặt cùng dòng với lệnh, nên chỉ copy phần lệnh.

## 1. Train mô hình

Bộ dữ liệu đã có sẵn nên có thể train ngay.

**Trên máy:**

```bash
python scripts/train.py --check
caffeinate -i python scripts/train.py
```

- Chạy lại đúng lệnh để tiếp tục từ checkpoint. Bấm Ctrl+C một lần để lưu rồi dừng.
- Muốn train hướng ngược lại, thêm `--direction vi2ede`.
- Kết quả nằm trong `runs/<hướng>/`.

**Trên Colab:**

1. Tải `data/dataset_colab.zip` vào thư mục `Hriam` trên Google Drive.
2. Mở `notebooks/train_colab.ipynb` trên Colab và bật GPU.
3. Chọn **Run all**. Khi phiên bị ngắt, chỉ cần **Run all** lại.

Kết quả nằm trong `Drive/Hriam/runs/<hướng>/`. Nếu dữ liệu thay đổi, hãy tải lại file zip.

## 2. Dựng lại dữ liệu

| Bước | Lệnh | Vào | Ra |
|---|---|---|---|
| 1. Cào Kinh Thánh | `python scripts/bible_scraper.py crawl` | Trang web | `data/raw/bible_html/`, `data/interim/{vi,ede}.jsonl`, `books.json` |
| 2. Căn câu | `python scripts/realign.py` | `vi.jsonl`, `ede.jsonl` | `parallel_aligned.jsonl`, `unmatched.jsonl` |
| 3. Phân tích từ điển | `python scripts/dict_parse.py` | `data/raw/dict_transcribed/` | `dictionary.jsonl` |
| 4. Tạo bộ dữ liệu | `python scripts/build_dataset.py` | Các file ở `data/interim/` | `data/dataset/`, `data/dataset_colab.zip` |

HTML đã cào được lưu lại nên chạy lại bước 1 không tải lại trang. Bước 2–4 chạy gộp được bằng `python scripts/train.py --rebuild-data`, lệnh này sẽ train tiếp ngay sau đó.

### Cào Kinh Thánh

Script tải từ **kinhthanh.httlvn.org** hai bản: Ê Đê `RRB` (Klei Aê Diê Blŭ 2015) và Việt `VI1934` (Kinh Thánh Tiếng Việt 1925).

```bash
python scripts/bible_scraper.py inspect --book sa --chapter 1
python scripts/bible_scraper.py crawl --limit 10
caffeinate -i python scripts/bible_scraper.py crawl
```

Cào toàn bộ khoảng 2.400 trang, mất khoảng 1 giờ, mỗi trang cách nhau 1,5 giây để tránh làm quá tải server. Nếu bị ngắt, chạy lại đúng lệnh để tiếp tục.

### Căn câu

Hai bản đánh số câu khác nhau ở một số chương, ví dụ Gióp 38:39–41 của bản Ê Đê là Gióp 39:1–3 của bản Việt. `realign.py` căn theo nội dung nên ghép đúng các đoạn này. Kết quả hiện tại: 31.049 cặp, 258 cặp có số câu hai bản khác nhau, 14 câu không có cặp.

### Từ điển

`TuDienEDe.pdf` là bản scan, nên bản dùng chính là bản chép từng trang trong `data/raw/dict_transcribed/`, với mỗi dòng có dạng `mục từ (từ loại) | nội dung`. Dòng bắt đầu bằng `| ` nối tiếp mục từ của trang trước.

- **Sửa lỗi:** sửa các file này rồi chạy bước 3 và 4.
- **Chính tả:** `dictionary.jsonl` giữ đúng mặt chữ trong sách. Bộ dữ liệu cuối quy một số từ về chính tả Kinh Thánh, ví dụ `hơ̆ng` thành `hŏng`, danh sách ở `data/dataset/spelling_map.json`.
- **Còn thiếu:** bản scan thiếu trang 146–147 của sách, đoạn từ `Tli tlia` đến `Trač`. Nếu có sách giấy, hãy chép thành file mới trong cùng thư mục.

## 3. Các file dữ liệu

| Đường dẫn | Nội dung |
|---|---|
| `data/raw/TuDienEDe.pdf`, `GiaiMaTiengEDE.pdf` | Hai file PDF gốc |
| `data/raw/bible_html/` | HTML đã cào |
| `data/raw/dict_transcribed/` | Bản chép tay 162 trang từ điển |
| `data/interim/vi.jsonl`, `ede.jsonl` | Kinh Thánh từng bản |
| `data/interim/books.json` | Đối chiếu mã sách của trang với mã USFM |
| `data/interim/parallel_aligned.jsonl` | Cặp câu đã căn theo nội dung |
| `data/interim/unmatched.jsonl` | Câu chỉ có ở một bản |
| `data/interim/dictionary.jsonl` | Từ điển có cấu trúc |
| `data/dataset/` | `train`, `dev_*`, `test_*`, `rejected`, `spelling_map.json`, `stats.json` |

## 4. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Train báo thiếu dữ liệu | Chạy `python scripts/train.py --rebuild-data` |
| Colab báo tràn bộ nhớ nhiều lần | Giảm các số trong `BATCH_BY_LENGTH` |
| Cào xong bị thiếu câu hoặc lẫn rác | HTML của trang có thể đã đổi. Xem `data/raw/bible_html/RRB/sa/1.html` và chỉnh `parse_chapter` |
| Cảnh báo "dò được X sách (kỳ vọng 66)" | Kiểm tra `data/interim/books.json` |
| Muốn cào lại từ đầu | Xoá `data/raw/bible_html/`. **Đừng xoá cả `data/`**, vì bản chép tay và PDF gốc nằm ở đó |

## 5. Bản quyền

- Bản tiếng Việt 1925 thuộc phạm vi công cộng.
- Bản Ê Đê 2015 nhiều khả năng còn bản quyền, và trang web ghi bản quyền thuộc về kinhthanh.httlvn.org.
- Dùng để nghiên cứu nội bộ thì rủi ro thấp. Muốn công bố dữ liệu hoặc làm sản phẩm, hãy xin phép HTTLVN hoặc Hội Thánh Ê Đê.
