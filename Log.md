# PES 2026 WEB — V1.10.70 Hybrid Smooth Room + Rank Frames

## Nâng cấp
- Khôi phục khung Rank trong phòng đấu cho cả chủ phòng và khách.
- Dùng ảnh trong `static/rank_frames/<rank-slug>.png` của bộ static V1.10.64c.
- Không còn tải lại toàn bộ trang khi trạng thái phòng thay đổi.
- Thao tác Sẵn sàng, Quay đội, Gửi kết quả, Xác nhận, Đá tiếp và Thoát phòng được gửi bằng `fetch`, sau đó chỉ thay nội dung phòng đấu.
- Giữ API trạng thái nhẹ 4 giây/lần; khi có thay đổi chỉ tải lại nội dung phòng, không nháy trắng toàn trang.
- Giữ backend Hybrid ổn định từ V1.10.68 và bố trí nút của V1.10.69.

## Cách dùng ảnh
Sau khi giải nén, copy thư mục `static` đầy đủ của V1.10.64c vào dự án. Giữ file `static/style.css` của bản V1.10.70, không ghi đè bằng CSS cũ.
