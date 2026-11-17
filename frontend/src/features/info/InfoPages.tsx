import { Link } from "react-router-dom";
import { PageHead } from "../../components/ui";

export function AboutPage() {
  return (
    <div className="wrap page narrow prose">
      <PageHead eyebrow="Về dự án" title="Hriăm — nền tảng ngôn ngữ và văn hoá Ê Đê" />
      <p>Hriăm giúp cộng đồng sử dụng, học tập, lưu trữ và phát triển tiếng Ê Đê, đồng thời làm cầu nối giao tiếp Ê Đê – Kinh.
        Đây không chỉ là công cụ dịch máy mà là một vòng tuần hoàn: người dùng tra cứu và đóng góp, chuyên gia xác minh,
        dữ liệu đã duyệt được phát hành thành phiên bản và làm bản dịch tốt hơn.</p>
      <h2>Nguyên tắc</h2>
      <ul>
        <li>Dữ liệu chính thức chỉ gồm nội dung đã xác minh, có nguồn và quyền sử dụng rõ ràng.</li>
        <li>AI chỉ gợi ý; bản dịch máy luôn được gắn nhãn “Bản nháp máy dịch”.</li>
        <li>Mỗi nghĩa có bằng chứng riêng; khác ngữ cảnh không có nghĩa là mâu thuẫn.</li>
        <li>Tôn trọng biến thể địa phương; chuẩn chữ viết do người có chuyên môn Ê Đê xác nhận.</li>
        <li>Bài đăng công khai không mặc nhiên trở thành dữ liệu huấn luyện.</li>
      </ul>
      <h2>Dữ liệu hiện có</h2>
      <p>Từ điển được số hoá từ cuốn Từ điển Êđê – Việt (bản scan, thiếu trang sách 146–147). Các nghĩa đang ở trạng thái
        “Chưa xác minh” cho tới khi chuyên gia rà soát, và quyền sử dụng sách đang chờ xin phép. Mô hình dịch là NLLB-200 tinh chỉnh,
        giấy phép phi thương mại.</p>
      <p><Link to="/contribute">Đóng góp</Link> · <Link to="/community">Cộng đồng</Link></p>
    </div>
  );
}

export function RulesPage() {
  return (
    <div className="wrap page narrow prose">
      <PageHead eyebrow="Cộng đồng" title="Quy tắc cộng đồng" />
      <p>Tiếng Ê Đê, phương ngữ, dấu phụ hay chủ đề văn hoá không bao giờ là vi phạm. Không được đăng:</p>
      <ul>
        <li>Quấy rối, bắt nạt, đe doạ; ngôn từ thù ghét hoặc phân biệt đối xử.</li>
        <li>Bạo lực, tự hại, nội dung nguy hiểm; nội dung tình dục không phù hợp.</li>
        <li>Spam, quảng cáo rác, lừa đảo, liên kết độc hại.</li>
        <li>Thông tin cá nhân của người khác khi chưa được phép; nội dung vi phạm bản quyền; nội dung giả mạo.</li>
      </ul>
      <h2>Kiểm duyệt</h2>
      <p>Mọi bài viết và bình luận được kiểm tra trước khi hiển thị. Nội dung có tiếng Ê Đê hoặc chưa rõ sẽ do người kiểm duyệt
        xem trực tiếp; việc chờ duyệt không tính là vi phạm.</p>
      <h2>Strike và khoá tài khoản</h2>
      <p>Mỗi vi phạm được người kiểm duyệt xác nhận là một strike. Strike 1–3: nội dung bị từ chối kèm cảnh cáo. Strike thứ 4:
        tài khoản bị khoá. Bạn luôn có thể <Link to="/community/appeals">khiếu nại</Link>; khiếu nại được chấp nhận sẽ huỷ strike tương ứng.</p>
    </div>
  );
}

export function PrivacyPage() {
  return (
    <div className="wrap page narrow prose">
      <PageHead eyebrow="Quyền riêng tư" title="Quyền riêng tư và đồng ý sử dụng dữ liệu" />
      <ul>
        <li><b>Tách mục đích:</b> công bố, nghiên cứu, huấn luyện mô hình là các lựa chọn riêng; không mục nào được suy ra từ mục khác.</li>
        <li><b>Số điện thoại:</b> không lưu dạng rõ; chỉ lưu mã HMAC có khoá để ngăn đăng ký lại sau khi tài khoản bị khoá.</li>
        <li><b>Lịch sử dịch:</b> mặc định không lưu; bạn bật/tắt và xoá trong Hồ sơ.</li>
        <li><b>Hội thoại:</b> không lưu âm thanh hay nội dung hội thoại.</li>
        <li><b>Đóng góp bị từ chối:</b> nội dung bị xoá, chỉ giữ thông tin kiểm toán tối thiểu (mã, thời gian, mã lý do).</li>
        <li><b>Dịch máy:</b> chạy trên máy chủ của dự án, không gửi văn bản tới bên thứ ba.</li>
      </ul>
      <p className="muted small">Chính sách này là mô tả kỹ thuật/sản phẩm, chưa qua rà soát pháp lý.</p>
    </div>
  );
}

export function NotFound() {
  return (
    <div className="wrap page narrow">
      <PageHead eyebrow="404" title="Không tìm thấy trang" />
      <Link className="btn primary" to="/">Về trang chủ</Link>
    </div>
  );
}
