# Collap_V1.13.3b — Khôi phục cảnh báo thoát phòng sau khi Sẵn Sàng

- Nền áp dụng: `Collap_V1.13.2` + các file của `Collap_V1.13.3a`.
- Ngày: 18/07/2026 — múi giờ Asia/Bangkok.
- Không cần chạy SQL Supabase.

## Nguyên nhân

Trong giao diện phòng mới, nút `Thoát Phòng` của khách luôn gọi route `room_guest_forfeit` và chỉ hiện cảnh báo chung `Bạn chắc chắn muốn thoát phòng?`.
Vì route này là luồng bỏ cuộc, khách có thể bị trừ 20 RP ngay cả khi chưa bấm `Sẵn Sàng`.
Luồng rời phòng không mất RP (`room_leave`) vẫn còn trong backend nhưng không được nút giao diện sử dụng đúng điều kiện.

## Logic sau khi sửa

- Khách **chưa Sẵn Sàng**:
  - Nút Thoát Phòng gọi `room_leave`.
  - Cảnh báo ghi rõ không bị trừ RP.
  - Phòng vẫn được giữ lại cho chủ phòng.
- Khách **đã Sẵn Sàng**:
  - Nút Thoát Phòng gọi `room_guest_forfeit`.
  - Cảnh báo ghi rõ bị tính là bỏ cuộc và trừ 20 RP.
- Backend chặn gửi POST trực tiếp vào route bỏ cuộc khi khách chưa sẵn sàng, tránh bị trừ điểm sai.
- Khi đã quay đội, đang thi đấu hoặc chờ xác nhận kết quả, cơ chế bỏ cuộc −20 RP vẫn giữ nguyên.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `templates/room_detail.html` | khoảng dòng 165–185 | Tách nút thoát theo trạng thái `guest_ready`; khôi phục cảnh báo −20 RP sau khi sẵn sàng |
| `modules/room_rematch_routes.py` | khoảng dòng 25–38 | Thêm khóa backend không phạt khách chưa sẵn sàng khi gửi POST trực tiếp |

## Kiểm tra

- Python compile module: đạt.
- Jinja parse template: đạt.
- Không thay đổi route hoặc URL hiện có.
- Không sửa công thức RP.
- Không sửa database hoặc `created_at`.
