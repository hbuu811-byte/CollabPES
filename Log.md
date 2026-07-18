# Collap_V1.13.3c — Modal thoát phòng đồng bộ giao diện game

- Phiên bản nền: `Collap_V1.13.2` + `Collap_V1.13.3a` + `Collap_V1.13.3b`.
- Ngày giờ: 18/07/2026 17:31 — múi giờ Asia/Bangkok.
- Phạm vi: chỉ giao diện xác nhận thoát phòng.
- Không sửa backend, công thức RP, database hoặc route.
- Không cần chạy SQL Supabase.

## Lỗi giao diện

Nút `Thoát Phòng` đang dùng `window.confirm()` của trình duyệt nên hiện hộp thoại trắng mặc định, không đồng bộ với giao diện tối màu của PES Arena.

## Nội dung đã sửa

- Bỏ hộp thoại trình duyệt tại các nút thoát phòng liên quan.
- Thêm modal tối màu nằm chính giữa màn hình, có lớp làm mờ nền.
- Modal tự đổi nội dung theo từng trường hợp:
  - Chưa Sẵn Sàng: thông báo `KHÔNG TRỪ RP` màu xanh.
  - Đã Sẵn Sàng hoặc trận đã bắt đầu: cảnh báo `−20 RP` màu đỏ.
  - Chủ phòng chưa có đối thủ: cảnh báo phòng sẽ bị đóng màu vàng.
- Nút xác nhận đổi theo hành động: `Rời phòng`, `Bỏ cuộc và thoát`, hoặc `Thoát và đóng phòng`.
- Có thể đóng modal bằng nút `×`, nút `Ở lại phòng`, bấm vùng nền tối hoặc phím `Esc`.
- Khi đã bấm xác nhận, nút chuyển thành `Đang xử lý...` và bị khóa để tránh gửi lệnh hai lần.
- Giữ nguyên route và quy tắc RP đã sửa trong `Collap_V1.13.3b`.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `templates/room_detail.html` | dòng 176–225 | Thay `confirm()` của nút thoát trước khi bắt đầu bằng dữ liệu modal theo trạng thái |
| `templates/room_detail.html` | dòng 376–408 | Thay `confirm()` khi đã quay đội/đang thi đấu bằng modal cảnh báo `−20 RP` |
| `templates/room_detail.html` | dòng 459–480 | Thêm cấu trúc modal giữa màn hình |
| `templates/room_detail.html` | dòng 831–917 | Thêm JavaScript mở, đóng và gửi form an toàn |
| `static/style.css` | dòng 4040–4222 | Thêm giao diện modal desktop/mobile theo tông xanh đen, vàng, đỏ và xanh lá |

## File không thay đổi

- `modules/room_rematch_routes.py`: giữ nguyên khóa backend của `Collap_V1.13.3b`.
- `app.py`: không sửa để tránh ghi đè các nâng cấp khác.
- Không sửa dữ liệu Supabase.

## Kiểm tra

- Jinja parse `templates/room_detail.html`: đạt.
- JavaScript modal kiểm tra cú pháp bằng `node --check`: đạt.
- Các hộp `confirm()` liên quan đến thoát phòng đã được loại bỏ.
- Hai hộp xác nhận không liên quan đến thoát phòng — gửi/rút tranh chấp — được giữ nguyên.
- Không thay đổi URL, method POST hoặc tên endpoint.
