# Collap_V1.13.3lv1.2

- Ngày giờ: 19/07/2026, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3lv1.1.
- Phạm vi: ổn định vòng đời polling/request; không thay đổi RP, bỏ cuộc, lịch sử đấu, modal hoặc dữ liệu Supabase.

## Nội dung nâng cấp

### 1. `static/js/pes_polling.js`
- Chỉ đăng ký bộ listener `pagehide/pageshow/beforeunload` một lần, kể cả file bị nạp lặp.
- Giữ một registry poller và request dùng chung trên `window`.
- `fetchJson()` không còn cố parse JSON đối với phản hồi HTML/rỗng, tránh lỗi JavaScript phụ.

### 2. `static/js/session-timeout.js`
- Thêm khóa dùng chung cho `/api/session/activity` và API kiểm tra hết hạn phiên.
- Không gửi activity khi tab ẩn, trang đang tạm dừng hoặc request trước chưa xong.
- Sửa lỗi quay lại trang bằng Back/Forward Cache làm bộ đếm tự đăng xuất bị dừng vĩnh viễn.
- Khi rời trang thật sự, dọn timer và listener; khi quay lại từ BFCache, khởi động lại đúng một lần.
- Chỉ ghi nhận mốc đã đồng bộ activity sau khi server phản hồi thành công.

### 3. `templates/base.html`
- Thêm khóa request dùng chung cho thông báo hệ thống và online count.
- Không parse JSON khi API trả phản hồi lỗi/rỗng.
- Không tạo polling mới và không đổi chu kỳ polling hiện hành.

### 4. `templates/room_detail.html`
- Dừng toàn bộ polling phòng/chat khi rời trang.
- Nhận diện phiên đăng nhập hết hạn hoặc API chuyển về `/login`; dừng poller và hiển thị thông báo thay vì tiếp tục gọi request lỗi.
- Giữ nguyên AJAX cập nhật phòng, bảo vệ bản nháp tỷ số, chat JSON, modal thoát phòng và toàn bộ giao diện trước đó.

### 5. `app.py`
- Chỉ tăng `APP_VERSION` thành `Collap_V1.13.3lv1.2` để tách cache CSS/JS đúng phiên bản.

## File cần chép đè
- `app.py`
- `static/js/pes_polling.js`
- `static/js/session-timeout.js`
- `templates/base.html`
- `templates/room_detail.html`

Không cần chạy SQL Supabase.
