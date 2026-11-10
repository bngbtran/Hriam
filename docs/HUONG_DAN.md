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

```bash
python scripts/train.py --check
caffeinate -i python scripts/train.py
```

- Chạy lại đúng lệnh để tiếp tục từ checkpoint. Bấm Ctrl+C một lần để lưu rồi dừng.
- Muốn train hướng ngược lại, thêm `--direction vi2ede`.
- Kết quả nằm trong `runs/<hướng>/`.
- Dịch thử bằng mô hình đã train: `python scripts/translate.py "câu Ê Đê"`. Thêm `--model base` để so với NLLB gốc, `--file` để dịch cả file.

### Train theo văn nói hằng ngày

Khoảng 80% dữ liệu là Kinh Thánh, nên mô hình train thẳng sẽ dịch giọng Kinh Thánh ("Các ngươi…", "bèn…"). `scripts/train_daily.sh` train hai giai đoạn để dịch gần lời ăn tiếng nói hằng ngày:

```bash
bash scripts/train_daily.sh ede2vi
bash scripts/train_daily.sh vi2ede
```

| Bước | Việc | Kết quả |
|---|---|---|
| 1 | Cào Kinh Thánh tiếng Việt **Bản Phổ Thông** (tiếng Việt hiện đại), căn câu, dựng bộ dữ liệu | `data/interim/vi_bpt.jsonl`, `data/dataset_bpt/` |
| 2 | Dựng bộ dữ liệu văn nói: ví dụ và nghĩa trong từ điển, câu hội thoại, cộng 3.000 câu Kinh Thánh ngắn để không quên | `data/dataset_noi/` |
| 3 | Giai đoạn nền: 3 epoch trên toàn bộ dữ liệu | `runs/<hướng>-nen/` |
| 4 | Giai đoạn văn nói: 4 epoch, learning rate nhỏ hơn, bắt đầu từ mô hình nền; chọn mô hình tốt nhất theo tập câu đời thường | `runs/<hướng>-noi/` |
| 5 | Đặt mô hình văn nói làm mặc định cho `translate.py` | `runs/<hướng>/best` |

- **Thời gian:** lần đầu cào bản Phổ Thông mất khoảng 30–60 phút. Giai đoạn nền khoảng 8–9 giờ, giai đoạn văn nói khoảng 1–2 giờ trên Apple M5 Pro.
- **Tiếp tục:** chạy lại đúng lệnh là tiếp tục từ chỗ dừng; bước đã xong được bỏ qua. Muốn train lại một giai đoạn thì xoá thư mục `runs/<hướng>-nen` hoặc `runs/<hướng>-noi`.
- **Tuỳ chỉnh:** `VI_VERSION=VI1934` dùng lại bản 1925 có sẵn, không cần cào. `EPOCHS_NEN`, `EPOCHS_NOI`, `LR_NOI` đổi số epoch và learning rate. `TRAIN_ARGS="--limit 32" EPOCHS_NEN=1 EPOCHS_NOI=1` chạy thử vài phút để kiểm tra; chạy thử xong nhớ xoá `runs/` trước khi train thật.
- **Đánh giá:** `runs/<hướng>-noi/test_results.json` có điểm trên `test_dict` và `test_hoithoai` (câu đời thường) và `test_bible` (để xem mô hình có quên Kinh Thánh không).

**Câu hội thoại là yếu tố quan trọng nhất.** Ví dụ trong từ điển phần lớn là câu ngắn. Mỗi câu hội thoại do người bản ngữ dịch giúp mô hình nói tự nhiên hơn nhiều so với thêm Kinh Thánh. Danh sách câu cần dịch và cách đóng góp nằm ở [data/raw/hoi_thoai/README.md](../data/raw/hoi_thoai/README.md). Sau khi thêm câu, xoá `runs/<hướng>-noi` rồi chạy lại lệnh; giai đoạn nền không cần train lại.

## Web dịch

Thư mục `web/` là một web tĩnh: HTML, CSS và JavaScript thuần, không framework, không bước build. Mọi xử lý chạy trên trình duyệt.

| Việc | Lệnh |
|---|---|
| Xem thử trên máy | `python -m http.server 8000 -d web`, mở http://127.0.0.1:8000 |
| Cập nhật dữ liệu web sau khi sửa từ điển hoặc dataset | `python scripts/export_web_data.py` |
| Bỏ Kinh Thánh khỏi web | `python scripts/export_web_data.py --no-bible` |
| Sinh lại logo và hoa văn | `python scripts/make_brand.py` (xem [BRAND.md](BRAND.md)) |

Không mở thẳng file `index.html` bằng trình duyệt: trình duyệt chặn đọc file dữ liệu, nên phải chạy qua web server như trên.

**Deploy:** đưa nguyên thư mục `web/` lên host tĩnh bất kỳ.

- **Netlify hoặc Cloudflare Pages:** kéo thả thư mục `web/` vào trang tạo site.
- **GitHub Pages:** chọn deploy từ nhánh, hoặc dùng GitHub Actions với thư mục `web/`. Repo private cần gói GitHub trả phí mới bật được Pages.
- **Vercel:** tạo project, đặt Root Directory là `web`, Framework là Other, để trống lệnh build.

**Bản quyền:** web tĩnh cho phép ai cũng tải nguyên `web/data/pairs.json`, gồm cả câu Kinh Thánh Ê Đê 2015 nhiều khả năng còn bản quyền. Nếu web công khai, nên xuất lại bằng `--no-bible`.

Link có thể điền sẵn câu: `?dir=ede2vi&text=Jŭ msĕ si ak` hoặc `?q=hriăm#tra-tu`.

## 2. Dựng lại dữ liệu

| Bước | Lệnh | Vào | Ra |
|---|---|---|---|
| 1. Cào Kinh Thánh | `python scripts/bible_scraper.py crawl` | Trang web | `data/raw/bible_html/`, `data/interim/{vi,ede}.jsonl`, `books.json` |
| 2. Căn câu | `python scripts/realign.py` | `vi.jsonl`, `ede.jsonl` | `parallel_aligned.jsonl`, `unmatched.jsonl` |
| 3. Dựng từ điển | Xem [data/dictionary/README.md](../data/dictionary/README.md) | `data/verified/` | `data/dictionary/dictionary_full.json` |
| 4. Tạo bộ dữ liệu | `python scripts/build_dataset.py` | Các file ở `data/interim/` | `data/dataset/` |

HTML đã cào được lưu lại nên chạy lại bước 1 không tải lại trang. Bước 2 và 4 chạy gộp được bằng `python scripts/train.py --rebuild-data`, lệnh này sẽ train tiếp ngay sau đó.

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

`TuDienEDe.pdf` là bản scan, nên bản dùng chính là bản chép từng trang đã đối chiếu trong `data/verified/AC/` (A–Č) và `data/verified/DY/` (D–Y), với mỗi dòng có dạng `mục từ (từ loại) | nội dung`. Dòng bắt đầu bằng `| ` nối tiếp mục từ của trang trước. `data/raw/dict_transcribed/` là bản chép lần đầu, chỉ dùng để ghi lại các chỗ đã sửa.

- **Sửa lỗi:** sửa file trong `data/verified/`, dựng lại từ điển theo `data/dictionary/README.md`, rồi chạy bước 4.
- **Chính tả:** từ điển giữ đúng mặt chữ trong sách. Sách viết `ŏ` giống Kinh Thánh, nhưng có `ê̆`, `ô̆` mà Kinh Thánh không dùng. Bộ dữ liệu cuối quy các từ này về chính tả Kinh Thánh, ví dụ `đuê̆` thành `đuĕ`, danh sách ở `data/dataset/spelling_map.json`.
- **Còn thiếu:** bản scan thiếu trang 146–147 của sách, đoạn từ `Tli tlia` đến `Trač`. Nếu có sách giấy, hãy chép thành file mới trong cùng thư mục.

## 3. Các file dữ liệu

| Đường dẫn | Nội dung |
|---|---|
| `data/raw/TuDienEDe.pdf`, `GiaiMaTiengEDE.pdf` | Hai file PDF gốc |
| `data/raw/bible_html/` | HTML đã cào |
| `data/raw/dict_transcribed/` | Bản chép tay lần đầu 162 trang từ điển |
| `data/verified/AC/`, `DY/` | Bản chép đã đối chiếu, nguồn chính của từ điển |
| `data/dictionary/` | Từ điển có cấu trúc (JSON, Excel), xem README trong thư mục |
| `data/interim/vi.jsonl`, `ede.jsonl` | Kinh Thánh từng bản |
| `data/interim/books.json` | Đối chiếu mã sách của trang với mã USFM |
| `data/interim/parallel_aligned.jsonl` | Cặp câu đã căn theo nội dung |
| `data/interim/unmatched.jsonl` | Câu chỉ có ở một bản |
| `data/dataset/` | `train`, `dev_*`, `test_*`, `rejected`, `spelling_map.json`, `stats.json` |

## 4. Xử lý sự cố

| Hiện tượng | Cách xử lý |
|---|---|
| Train báo thiếu dữ liệu | Chạy `python scripts/train.py --rebuild-data` |
| Máy chậm hẳn hoặc tràn bộ nhớ khi train | Giảm các số trong `BATCH_BY_LENGTH` ở `scripts/train.py` |
| Cào xong bị thiếu câu hoặc lẫn rác | HTML của trang có thể đã đổi. Xem `data/raw/bible_html/RRB/sa/1.html` và chỉnh `parse_chapter` |
| Cảnh báo "dò được X sách (kỳ vọng 66)" | Kiểm tra `data/interim/books.json` |
| Muốn cào lại từ đầu | Xoá `data/raw/bible_html/`. **Đừng xoá cả `data/`**, vì bản chép tay và PDF gốc nằm ở đó |

## 5. Bản quyền

- Bản tiếng Việt 1925 thuộc phạm vi công cộng.
- Bản Ê Đê 2015 nhiều khả năng còn bản quyền, và trang web ghi bản quyền thuộc về kinhthanh.httlvn.org.
- Bản Phổ Thông (BPT) dùng cho train văn nói là bản dịch hiện đại, nhiều khả năng cũng còn bản quyền. Chỉ dùng trong nhóm để nghiên cứu.
- Dùng để nghiên cứu nội bộ thì rủi ro thấp. Muốn công bố dữ liệu hoặc làm sản phẩm, hãy xin phép HTTLVN hoặc Hội Thánh Ê Đê.
