# Collap_V1.13.3lv3.3 — Giảm request trong phòng đấu

- Ngày giờ: 19/07/2026 — múi giờ Asia/Bangkok.
- Bản nền bắt buộc: `Collap_V1.13.3lv3.2`.
- Loại gói: trình vá an toàn; chỉ sửa đúng ba file liên quan.
- SQL Supabase: không cần.

## Kết quả rà soát

Request trùng đã được khóa ở `lv3.2`, nhưng tổng request vẫn cao vì nhiều vòng hợp lệ cùng hoạt động trong phòng:

1. `/state` chạy nhanh cố định ngay cả khi phòng không thay đổi.
2. Chat phòng gọi mỗi 15 giây.
3. Heartbeat, lời mời và thông báo hệ thống vẫn chạy khi người chơi đang ở trong phòng.
4. `updated_at` nằm trong `state_key`; cập nhật phụ cũng có thể làm tải thêm fragment `/view`.

## Nội dung sửa

### `app.py`

- Tăng version lên `Collap_V1.13.3lv3.3`.
- Bỏ `updated_at` khỏi `build_room_state_key()` vì các trường làm đổi giao diện đã có trong khóa.
- Tận dụng `/api/room/<id>/state` để cập nhật online tối đa một lần mỗi 60 giây.
- Nhờ đó trang phòng không cần gửi thêm request `/heartbeat` riêng.

### `templates/base.html`

Khi đang ở trang phòng:

- Không chạy heartbeat riêng.
- Không kiểm tra `/api/invites/pending`.
- Không chạy active-room.
- Không chạy chat sảnh.
- Không polling thông báo hệ thống.

Khi ở ngoài phòng:

- Heartbeat: 60 giây.
- Lời mời: 18 giây.
- Active room: 30–45 giây.
- Chat sảnh khi mở: 30 giây.
- Thông báo hệ thống: 90 giây.

### `templates/room_detail.html`

- `/state` dùng chu kỳ thích ứng:
  - phản hồi nhanh ngay sau khi phòng thay đổi;
  - sau 4 lần không đổi bắt đầu giãn;
  - sau 8 lần không đổi có thể giãn tối đa 18 giây;
  - khi có thay đổi hoặc người dùng thao tác, lập tức quay về chu kỳ nhanh.
- Chat phòng:
  - 30 giây khi khung chat đang nằm trong màn hình;
  - 60 giây khi khung chat ngoài vùng nhìn;
  - 120 giây khi tab ẩn.
- Không thêm reload toàn trang.
- Không sửa khóa request hoặc logic giữ ô tỷ số của `lv3.2`.

## Ước lượng giảm request trong phòng ổn định

So với `lv3.2`, mỗi người chơi trong phòng sẽ loại bỏ hoàn toàn:

- 1 vòng lời mời.
- 1 vòng heartbeat.
- 1 vòng thông báo hệ thống.

Đồng thời:

- `/state` tự giãn khi không có thay đổi.
- Chat giảm khoảng một nửa hoặc hơn.
- Các cập nhật phụ không còn tự kích hoạt `/view` chỉ vì `updated_at` đổi.

Mức giảm thực tế phụ thuộc trạng thái phòng và số tin chat, nhưng trong giai đoạn thi đấu ổn định dự kiến giảm khoảng 45–70% số request nền của trang phòng.

## File được sửa sau khi chạy

| File | Nội dung |
|---|---|
| `app.py` | Version, state key, gộp online presence vào `/state` |
| `templates/base.html` | Tắt poller toàn cục trong phòng; giãn poller ngoài phòng |
| `templates/room_detail.html` | Polling `/state` thích ứng và giãn chat phòng |

## Không thay đổi

- Không sửa RP hoặc phạt bỏ cuộc.
- Không sửa lịch sử trận.
- Không sửa Admin.
- Không sửa modal hoặc giao diện phòng.
- Không sửa CSS/JS cache đã có.
- Không thay đổi cấu trúc Supabase.

## Cách áp dụng

1. Giải nén ZIP.
2. Chép ba file trong ZIP vào thư mục gốc dự án `Collap_V1.13.3lv3.2`.
3. Nhấp đúp `APPLY_Collap_V1.13.3lv3.3.bat`.
4. Commit đúng ba file được báo đã sửa.
5. Không commit thư mục `.collap_v1_13_3lv3_3_backup`.
