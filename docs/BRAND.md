# Bộ nhận diện Hriăm

Bản trình bày đầy đủ, có hình minh hoạ, nằm ở `web/brand.html` (mở từ chân trang web, mục "Bộ nhận diện"). Tài liệu này tóm tắt các quy tắc và căn cứ.

Mọi file hình trong `web/assets/brand/` được sinh bằng `python scripts/make_brand.py`. Muốn sửa hình thì sửa bản vẽ trong script, không sửa tay các file SVG.

## Một nguồn cho cả web

`scripts/make_brand.py` là nơi duy nhất định nghĩa nhận diện. Script sinh ra:

| File | Nội dung |
|---|---|
| `colors.css` | Sáu màu gốc dạng biến CSS (`--cham`, `--cham-xanh`, `--do`, `--vang`, `--nga`, `--xanh`), nạp trước `style.css` ở mọi trang |
| `mark.svg`, `favicon.svg`, `logo.svg`, `logo-dark.svg` | Logo; chữ trong logo đã đổi thành nét vẽ nên hiển thị đúng phông ở mọi nơi |
| `motif-*.svg`, `icon-*.svg` | Hoạ tiết trên nền chàm, và bản nền trong suốt dùng trên nền sáng |
| `hem.svg`, `stripe.svg`, `texture.svg` | Các dải hoa văn và lưới nền |
| `og.png` | Ảnh xem trước 1200 × 630 khi chia sẻ link |

Lần đầu chạy, script tải hai phông Noto vào `scripts/.fonts/` (không đưa lên git) để đổi chữ thành nét vẽ.

`web/assets/style.css` không chứa mã màu thương hiệu nào. Mọi sắc độ được pha từ sáu màu gốc bằng `color-mix`, kể cả chế độ tối. Ngoài sáu màu gốc, chỉ có các màu bề mặt trung tính cho nền sáng: nền trang `#F6F1E7`, giấy `#FFFDF9`, mực `#1C1A17`, chữ phụ `#6F665B`, đường kẻ `#E6DDCC`.

**Thành phần dùng chung trên mọi trang:**

- **Đầu trang:** nền chàm có lưới chéo; biểu tượng cùng tên Hriăm và dòng phụ vàng "DỊCH VIỆT – Ê ĐÊ"; menu Dịch · Từ điển · Giới thiệu · Nhận diện, mục đang mở có gạch vàng.
- **Chân trang:** dải gấu váy, logo chữ, liên kết, ghi chú đồ án.
- **Trạng thái trống:** mỗi chỗ dùng đúng một hoạ tiết đơn lẻ. Chuồn chuồn cho "Nhập một câu để bắt đầu", rùa cho "Không tìm thấy câu tương tự", thằn lằn cho "Không tìm thấy mục từ".
- **Thẻ mục từ:** viền trên bằng dải sọc ngực áo.
- **Ảnh chia sẻ:** thẻ `og:image` trỏ tới `og.png`. Khi deploy, đổi thành đường dẫn đầy đủ có tên miền.

## Căn cứ từ tư liệu

| Điều tư liệu nói | Áp dụng vào Hriăm |
|---|---|
| Trang phục Ê Đê thường nền đen hoặc chàm; các màu chính là đen, đỏ, vàng, trắng; viền váy có thêm sợi xanh | Bảng màu sáu màu; chàm đen là màu nền chính |
| Dải hoa văn chiếm khoảng 1/4 đến 1/3 mặt vải, là hình học chạy dài liên tục, kèm đường thẳng song song và răng cưa | Hoa văn chỉ đặt thành dải ở mép khối; phần còn lại để trơn |
| Dải hoa văn dệt sát gấu váy, gấu áo, chân khố; áo nam có sọc ngang ở giữa thân | Dải "gấu váy" và dải "sọc ngực áo" |
| Hoạ tiết hay gặp: quả trám, cành trúc, rùa, thằn lằn, chuồn chuồn, chim, hoa lá | Năm hoạ tiết cách điệu: quả trám, rùa, thằn lằn, chuồn chuồn, răng cưa |
| Kỹ thuật Kteh (dệt kèm hạt cườm) dành cho lễ phục và gia đình khá giả | Không mô phỏng Kteh, không dùng tên này |

Nguồn:

- [Nghệ thuật trang trí trên thổ cẩm của người Ê Đê](https://nhandan.vn/nghe-thuat-trang-tri-tren-tho-cam-cua-nguoi-e-de-post886454.html), Nhân Dân, 2025.
- [Brocade art of the Ede ethnic minority](https://vietnamnet.vn/en/brocade-art-of-the-ede-ethnic-minority-793999.html), VietNamNet, 2021.
- [Traditional attire of the Ede](https://vietnam.vnanet.vn/english/print/traditional-attire-of-the-ede-408989.html), Vietnam Pictorial, 2025.

Các nguồn không nêu ý nghĩa riêng của từng màu hay từng hoạ tiết, nên Hriăm không gán ý nghĩa biểu tượng cho chúng.

## Ba nguyên tắc

1. **Vẽ trên lưới dệt:** mọi hình là bậc thang trên lưới ô vuông, không đường cong, không đường chéo trơn.
2. **Nền chàm, điểm màu:** chàm đen và nền sáng chiếm phần lớn; đỏ và vàng làm điểm nhấn; xanh chỉ điểm xuyết.
3. **Hoa văn ở viền:** dải hoa văn nằm ở mép khối như gấu váy, không phủ kín sau chữ cần đọc.

## Tên

- **Hriăm** trong tiếng Ê Đê nghĩa là *học* (Từ điển Ê Đê – Việt, trang 58).
- Luôn viết đúng dấu: `Hriăm`. Chỉ dùng `Hriam` không dấu ở nơi không gõ được dấu, như tên repo hay đường dẫn.
- Dòng phụ: **Dịch Việt – Ê Đê**, viết hoa toàn bộ khi đặt dưới logo.

## Logo: chữ H dệt

Hai dải sọc đỏ viền trắng đứng song song như hai dải dệt, tạo thành chữ H. Quả trám vàng – đỏ – trắng ở giữa làm nét ngang. Biểu tượng nằm trên nền chàm đen bo góc 20%, lưới 15 × 15 ô.

| File | Dùng khi |
|---|---|
| `logo.svg` | Logo đầy đủ trên nền sáng |
| `logo-dark.svg` | Logo đầy đủ trên nền chàm |
| `mark.svg`, `favicon.svg` | Biểu tượng riêng: favicon, ảnh đại diện, chỗ hẹp |

- Khoảng trống quanh logo ít nhất bằng 1/4 cạnh biểu tượng.
- Kích thước nhỏ nhất: biểu tượng 16 px, logo đầy đủ cao 32 px.
- Không kéo méo, xoay, đổi màu, làm mờ hay thêm bóng đổ.

## Màu

| Tên | Mã | Vai trò |
|---|---|---|
| Chàm đen | `#161722` | Nền chính: đầu trang, chân trang, nền biểu tượng |
| Chàm | `#2A3566` | Nền phụ |
| Đỏ | `#A8281E` | Nhấn chính: nút, liên kết, dải sọc |
| Vàng nghệ | `#E2A72E` | Nhấn phụ: chữ nhỏ trên nền chàm, quả trám |
| Trắng sợi bông | `#F3EDE1` | Chữ trên nền chàm, viền hoạ tiết |
| Xanh | `#3D5A9E` | Chỉ điểm xuyết trong dải hoa văn |

Nền trang sáng là `#F6F1E7`. Ở chế độ tối, nền là `#10111A` và đỏ sáng lên thành `#E05A47` để đủ tương phản. Các mã màu nằm trong `:root` của `web/assets/style.css`.

## Hoạ tiết và dải hoa văn

| File | Nội dung | Dùng ở |
|---|---|---|
| `motif-qua-tram.svg` | Quả trám (hình thoi) | Logo, dải gấu váy |
| `motif-rua.svg` | Rùa | Dải gấu váy |
| `motif-than-lan.svg` | Thằn lằn | Điểm nhấn đơn lẻ |
| `motif-chuon-chuon.svg` | Chuồn chuồn | Điểm nhấn đơn lẻ |
| `motif-rang-cua.svg` | Răng cưa | Dải gấu váy |
| `hem.svg` | Dải gấu váy: sọc đỏ, hàng chấm trắng, rùa xen quả trám, sọc vàng, răng cưa, sọc đỏ | Đáy đầu trang, đỉnh chân trang, đáy khối Giới thiệu |
| `stripe.svg` | Sọc ngực áo: đỏ, chỉ trắng, vàng, xanh | Đường phân cách, viền trên thẻ mục từ |
| `texture.svg` | Lưới chéo rất mờ | Chỉ trên nền chàm |

Các hoạ tiết là hình cách điệu mới, không chép một tấm vải hay một nghệ nhân cụ thể nào.

## Chữ

- **Noto Serif Display** (500–600): tên Hriăm, tiêu đề, mục từ.
- **Noto Sans** (400–700): nội dung, nút, nhãn.
- Nhãn nhỏ phía trên tiêu đề viết hoa, giãn chữ rộng: vàng trên nền chàm, đỏ trên nền sáng.

Hai phông Noto hiển thị đủ chữ Ê Đê (`ƀ`, `č`, `ñ`, `ĭ`, `ŏ`, `ŭ` và các chữ có dấu chồng như `ê̆`, `ơ̆`). Khi thay phông, hãy kiểm tra lại các chữ này.

## Giọng văn

- Tiếng Việt rõ ràng, ngắn gọn, xưng hô trung tính.
- Nói thẳng giới hạn của công cụ, ví dụ: "Bản ghép nghĩa theo từ điển, chưa theo ngữ pháp Ê Đê."
- Viết tên dân tộc là **Ê Đê**, và giữ đúng dấu khi trích chữ Ê Đê.

## Tôn trọng văn hoá

- Không gán ý nghĩa thiêng liêng hay nghi lễ cho hoạ tiết khi chưa có nguồn xác nhận.
- Không mô phỏng hoa văn Kteh, vốn gắn với lễ phục và gia đình quyền quý.
- Trước khi dùng nhận diện chính thức (in ấn, ra mắt công khai), hãy hỏi ý kiến người Ê Đê hoặc nghệ nhân dệt.
