import { Link } from "react-router-dom";
import { PageHead } from "../../components/ui";

const TIERS = [
  ["Công khai", "Ai cũng xem được, khi người kể/chủ sở hữu đồng ý."],
  ["Cộng đồng", "Chỉ thành viên đã đăng nhập."],
  ["Hạn chế", "Chỉ người được cộng đồng hoặc người kể cho phép."],
  ["Riêng tư / tạm giữ", "Lưu trữ, chưa công bố."],
];

export function CulturePage() {
  return (
    <div className="wrap page">
      <PageHead eyebrow="Văn hoá" title="Kho tư liệu văn hoá Ê Đê">
        Truyện kể, lời hát, tục ngữ, hình ảnh và âm thanh sẽ được lưu cùng người kể, địa phương, giấy phép và mức quyền truy cập do
        chủ thể tư liệu quyết định. Kho đang được chuẩn bị quy trình xin phép trước khi mở.
      </PageHead>
      <div className="principles">
        {TIERS.map(([t, d], i) => (
          <div key={t} className="principle"><span className="num">{i + 1}</span><h3>{t}</h3><p>{d}</p></div>
        ))}
      </div>
      <div className="alert info mt">
        Tư liệu nghi lễ, tri thức thiêng hoặc thông tin cộng đồng hạn chế sẽ không công khai mặc định. Trong lúc chờ, bạn có thể chia sẻ
        tục ngữ, thành ngữ qua <Link to="/contribute?type=phrase">Đóng góp</Link> hoặc thảo luận ở mục <Link to="/community?category=van-hoa">Văn hoá</Link>.
      </div>
    </div>
  );
}
