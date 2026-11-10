# Câu hội thoại Việt – Ê Đê

Thư mục này chứa câu nói hằng ngày do người bản ngữ dịch. Đây là nguồn quan trọng nhất để mô hình dịch tự nhiên, vì phần lớn dữ liệu hiện có là Kinh Thánh. Chỉ khoảng 1.000 câu tốt đã giúp mô hình nói tự nhiên hơn rõ rệt.

## Cách đóng góp

1. Chép `mau.tsv` thành file mới, ví dụ `nguoi_dich_hhen.tsv`. Mở bằng Excel, Google Sheets hoặc trình soạn thảo văn bản.
2. Mỗi dòng một cặp câu. Các cột cách nhau bằng phím Tab:
   - `vi`: câu tiếng Việt.
   - `ede`: câu tiếng Ê Đê, viết đúng dấu (ŏ, ĕ, ŭ, ƀ, č, ñ…).
   - `nguoi_dich`, `ghi_chu`: không bắt buộc.
3. Câu cần dịch có sẵn trong `cau_can_dich.txt`; có thể thêm câu khác.
4. Khi xuất từ Google Sheets, chọn định dạng "Tab-separated values (.tsv)".

Cũng có thể dùng file `.jsonl`, mỗi dòng `{"vi": "...", "ede": "..."}`.

## Lưu ý

- Chỉ đưa vào câu do người biết tiếng Ê Đê dịch hoặc kiểm tra. Không dùng câu do máy dịch.
- Dịch theo cách nói tự nhiên, không cần sát từng chữ.
- Một câu có nhiều cách nói thì ghi mỗi cách một dòng.
- `scripts/build_daily.py` tự chia khoảng 10% câu làm tập test và 10% làm tập dev, để đo xem mô hình dịch văn nói tốt đến đâu.
