# Collap_V1.13.3lv2.3

- Ngày giờ: 19/07/2026, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3lv2.2.
- Loại gói: bản vá, chỉ gồm các file cần chép đè.

## Lỗi đã xác định

API `/api/room/<room_id>/state` chỉ render fragment `_room_live_content.html` khi trạng thái phòng thay đổi. Fragment này sử dụng `system_features.room_chat_enabled` và `system_features.friendly_enabled`, nhưng route không truyền `system_features`. Vì vậy đúng lúc khách cần nhận người vừa vào phòng, đội vừa quay hoặc tỷ số mới, server có thể trả `503 temporary_render_error`; giao diện khách giữ nguyên như không nhận tín hiệu.

Phần lời mời cũng không có timer dự phòng. Nếu `static/js/pes_polling.js` chưa sẵn sàng hoặc tải lỗi, `configureInvitePolling()` thoát ngay và không gọi `/api/invites/pending`.

## Nội dung sửa

### `app.py`

- Tăng `APP_VERSION` lên `Collap_V1.13.3lv2.3`.
- Truyền đầy đủ `current_user` và `system_features` khi API state render fragment động.
- Giữ nguyên cơ chế không reload trang; API vẫn chỉ trả HTML của `#roomLiveContent` khi state key thay đổi.
- Thêm `Cache-Control: no-store` cho API lời mời để tránh trình duyệt/proxy giữ kết quả cũ.

### `templates/base.html`

- Vẫn ưu tiên đúng một poller lời mời của `PESNet`.
- Khởi động kiểm tra lời mời ngay cả khi `PESNet` chưa sẵn sàng; dùng đúng một timer dự phòng.
- Timer dự phòng có khóa request, dừng khi tab ẩn và tự chuyển về poller chuẩn khi `PESNet` xuất hiện.
- Không tạo hai luồng `/api/invites/pending` chạy song song.

## Không thay đổi

- Không sửa RP, công thức Rank hoặc dữ liệu Supabase.
- Không sửa lịch sử đấu, trận bỏ cuộc, modal thoát phòng.
- Không đưa lại `location.reload()` hoặc `window.location.reload()` vào phòng.
- Không thay đổi route quay đội, gửi tỷ số hoặc xác nhận kết quả.
- Không cần chạy SQL Supabase.

## File cần chép đè

- `app.py` — khoảng dòng 65, 3639–3685, 3747–3815.
- `templates/base.html` — khoảng dòng 866–940.
