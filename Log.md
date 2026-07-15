# V1.10.60 — Phòng đấu cập nhật từng phần bằng HTMX + Supabase Realtime

## Mục tiêu
- Loại bỏ việc tải lại toàn bộ trang khi trạng thái phòng thay đổi.
- Rút ngắn thời gian người còn lại nhận tỷ số và nút xác nhận.
- Giữ Supabase Realtime làm kênh thông báo chính; polling chỉ là dự phòng.

## Thay đổi chính
- Tạo `templates/partials/room_dynamic_state.html` làm khung trạng thái động của phòng đấu.
- Tạo endpoint `GET /room/<room_id>/state-fragment` để truy xuất lại đúng dữ liệu phòng từ Supabase và chỉ render phần HTML cần thay.
- Form **Gửi Kết Quả** dùng HTMX, khóa nút trong lúc gửi và thay riêng `#roomDynamicState`.
- Form **Xác Nhận** dùng HTMX, không redirect và không tải lại toàn trang.
- Backend gửi/xác nhận tỷ số vẫn dùng đúng logic kiểm tra quyền, trạng thái trận, cập nhật `matches`, `match_rooms` và tính RP hiện có.
- Thông báo thành công/lỗi của hai thao tác được trả ngay trong fragment.
- Supabase Realtime của `match_rooms` gọi cập nhật fragment sau khoảng 80 ms thay vì gọi `window.location.reload()`.
- Polling dự phòng khi Realtime chưa kết nối giảm từ 6 giây xuống 3 giây.
- Khi Realtime đã kết nối, polling kiểm tra an toàn giãn từ 45 giây lên 90 giây để giảm request thừa.
- Sau mỗi lần HTMX thay fragment, bộ đếm thời gian và `state_key` được khởi tạo lại đúng trạng thái mới.
- Nâng `APP_VERSION` lên `V1.10.60`.

## Không thay đổi
- Không thay schema hoặc tạo bảng Supabase mới.
- Không thay logic cộng/trừ RP.
- Chat phòng và Presence vẫn ưu tiên Supabase Realtime.
- Các form vẫn giữ `method` và `action` thông thường để fallback khi HTMX/CDN không tải được.

## Kiểm tra
- `app.py` biên dịch Python thành công.
- Toàn bộ template Jinja parse thành công.
- Không còn `window.location.reload()` trong `room_detail.html`.
