# Collap_V1.13.3d — Chủ phòng thoát sau khi khách Sẵn Sàng

- **Ngày giờ:** 18/07/2026 17:45, múi giờ Asia/Bangkok
- **Bản nền trực tiếp:** `Collap_V1.13.3c`
- **Bản gốc kiến trúc:** `Collap_V1.13.2`
- **Các bản đã đối chiếu:**
  - `Collap_V1.13.3b`: cơ chế khách rời phòng trước/sau Sẵn Sàng và phạt 20 RP.
  - `Collap_V1.13.3c`: modal xác nhận giữa màn hình đồng bộ giao diện game.
  - `Collap_V1.13.2`: route `room_leave` và cấu trúc module phòng đấu.

## Yêu cầu

Áp dụng quy tắc tương tự cho Chủ Phòng:

1. Khách chưa Sẵn Sàng: Chủ Phòng được thoát và đóng phòng, không bị trừ RP.
2. Khách đã Sẵn Sàng: Chủ Phòng thoát bị tính là bỏ cuộc và trừ 20 RP.
3. Hiển thị modal giữa màn hình, không dùng hộp `confirm()` mặc định của trình duyệt.
4. Gửi thông báo cho cả Chủ Phòng và Khách sau khi Chủ Phòng bỏ cuộc.

## Nội dung đã sửa

### `app.py`

- **Khoảng dòng 64–66:** nâng `APP_VERSION` từ `Collap_V1.13.3a` lên `Collap_V1.13.3d`.
- Không thay đổi công thức RP hoặc route khác trong `app.py`.

### `modules/room_access_routes.py`

- **Khoảng dòng 171–235 — route `room_leave`:**
  - Khóa luồng rời phòng không phạt khi `room.status = waiting_ready` và `guest_ready = true`.
  - Áp dụng cho cả Chủ Phòng và Khách.
  - Ngăn né phạt bằng cách gửi POST trực tiếp vào endpoint `/leave`.
  - Nếu trạng thái vừa thay đổi, người chơi được đưa lại phòng để xác nhận đúng luồng; không tự trừ RP sai.

### `modules/room_rematch_routes.py`

- **Khoảng dòng 86–163 — route mới `room_host_forfeit`:**
  - Chỉ Chủ Phòng thật sự được gọi route.
  - Chỉ chạy khi phòng đang `waiting_ready`, có khách và khách đã Sẵn Sàng.
  - Lệnh cập nhật có điều kiện đồng thời theo:
    - `id` phòng;
    - `status = waiting_ready`;
    - `guest_ready = true`.
  - Điều kiện trên tránh trừ RP nếu khách vừa bấm Hủy Sẵn Sàng cùng lúc.
  - Đóng phòng và đặt `guest_ready = false`.
  - Trừ Chủ Phòng 20 RP bằng hàm dùng chung `apply_room_abandon_penalty()`.
  - Tính thêm một trận thua cho Chủ Phòng, đặt streak về 0 theo logic hiện có.
  - Nếu phòng có `match_id` bất thường, lưu delta đúng phía Chủ Phòng: `delta1 = -20`, `delta2 = 0`.
  - Gửi thông báo cho Khách rằng Chủ Phòng bỏ cuộc; Khách không được cộng hoặc trừ RP.
  - Gửi thông báo cho Chủ Phòng về mức phạt và trận thua.
  - Chống bấm/gửi hai lần bằng update có điều kiện; request sau không bị trừ thêm.

### `templates/room_detail.html`

- **Khoảng dòng 164–221 — khu điều khiển khi phòng `waiting_ready`:**
  - Giữ nguyên nút của Khách từ `Collap_V1.13.3c`.
  - Bổ sung nút **Thoát Phòng** cho Chủ Phòng khi đã có khách.
  - Khách chưa Sẵn Sàng:
    - gọi route `room_leave`;
    - modal màu an toàn;
    - hiển thị `KHÔNG TRỪ RP`.
  - Khách đã Sẵn Sàng:
    - gọi route `room_host_forfeit`;
    - modal cảnh báo màu đỏ;
    - hiển thị `−20 RP`;
    - nút xác nhận ghi `Bỏ cuộc và đóng phòng`.
- Tái sử dụng modal và CSS của `Collap_V1.13.3c`; không cần sửa `static/style.css`.

## Logic cuối cùng

| Người thoát | Trạng thái khách | Kết quả |
|---|---|---|
| Khách | Chưa Sẵn Sàng | Rời phòng, không trừ RP |
| Khách | Đã Sẵn Sàng | Bỏ cuộc, trừ 20 RP |
| Chủ Phòng | Khách chưa Sẵn Sàng | Đóng phòng, không trừ RP |
| Chủ Phòng | Khách đã Sẵn Sàng | Bỏ cuộc, trừ 20 RP |

Đối thủ không được cộng RP trong các trường hợp bỏ cuộc này.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/room_access_routes.py modules/room_rematch_routes.py`: **đạt**.
- Import dự án sau khi ghép tuần tự `1.13.2 → 1.13.3a → 1.13.3b → 1.13.3c → 1.13.3d`: **đạt**.
- Phiên bản sau import: `Collap_V1.13.3d`.
- Tổng route Flask: **101**.
- Route mới: `POST /room/<room_id>/host-forfeit`.
- Route URL + HTTP method trùng: **không có**.
- Parse 24 template Jinja: **đạt**.
- Mô phỏng Chủ Phòng thoát khi khách đã Sẵn Sàng:
  - trừ điểm đúng một lần: **đạt**;
  - tạo hai thông báo: **đạt**;
  - đóng phòng: **đạt**.
- Mô phỏng gọi route phạt khi khách chưa Sẵn Sàng:
  - không trừ RP: **đạt**.
- Mô phỏng gửi trực tiếp POST vào `/leave` sau khi khách đã Sẵn Sàng:
  - bị chặn, không thể né phạt: **đạt**.
- Không cần SQL Supabase.

## Cài đặt

Bản này áp dụng sau `Collap_V1.13.3c`. Chép đè đúng các file trong ZIP vào thư mục gốc dự án, sau đó Commit, Push và triển khai trên nhánh test.
