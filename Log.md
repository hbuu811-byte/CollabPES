# Collap_V1.13.3h

- Ngày giờ: 18/07/2026, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3f.
- Phạm vi: chỉ sửa danh sách hiển thị khi bấm chuông thông báo.

## Nội dung sửa

- Chuông thông báo hiển thị tối đa 20 thông báo mới nhất còn hạn của người đang đăng nhập.
- Danh sách trong chuông gồm cả thông báo đã đọc và chưa đọc.
- Huy hiệu số trên chuông vẫn chỉ đếm số thông báo chưa đọc trong 20 mục đang hiển thị.
- Không thêm tiêu đề hoặc câu mô tả mới.
- Không thay đổi trang `/notifications`.
- Không thêm polling và không chạy lệnh xóa dữ liệu mỗi lần render trang.
- Giữ nguyên cơ chế: thông báo quá 7 ngày không hiển thị; dữ liệu được dọn khi tạo thông báo mới hoặc mở trang thông báo.

## File đã sửa

- `app.py` khoảng dòng 65, 3490–3538: tăng phiên bản; nạp 20 thông báo cho chuông và tính số chưa đọc.
- `modules/notification_service.py` khoảng dòng 8–18, 155–185: thêm hàm `list_bell_notifications()`.
- `templates/base.html` khoảng dòng 95–130: dùng danh sách 20 thông báo trong dropdown của chuông.

## Cài đặt

Chép đè ba file code vào bản Collap_V1.13.3f. Không cần chạy SQL Supabase.
