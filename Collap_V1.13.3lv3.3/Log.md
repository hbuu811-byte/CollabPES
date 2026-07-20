# Collap_V1.13.3lv3.2

- Ngày giờ: 19/07/2026 01:38, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3lv3.1.
- Mục tiêu: ưu tiên trải nghiệm người dùng, giảm nguy cơ request cũ chạy ngầm và tránh lỗi 403 chat sai.
- Phạm vi: chỉ sửa các file trực tiếp liên quan; không sửa RP, lịch sử đấu, giao diện lịch sử phòng, modal, cache hoặc SQL Supabase.

## Nội dung sửa

### 1. Sửa gửi chat phòng bị từ chối nhầm

- Route gửi chat trước đây so sánh trực tiếp `user["id"]` với ID chủ/khách.
- Khi một giá trị là số và giá trị còn lại là chuỗi, người đang ở đúng phòng vẫn có thể bị báo không thuộc phòng.
- Đã đổi sang `_same_user_id()` giống API đọc chat.
- Quyền bảo mật giữ nguyên: người ngoài phòng vẫn không thể gửi chat.

### 2. Không dừng toàn bộ hệ thống khi chỉ thao tác trong phòng

- Các thao tác như Sẵn Sàng, Hủy Sẵn Sàng, quay đội, gửi kết quả, xác nhận kết quả và gửi chat chỉ dừng:
  - polling trạng thái phòng;
  - polling chat phòng;
  - request `/state` hoặc chat đang chạy.
- Heartbeat, lời mời và thông báo hệ thống không bị dừng sớm trong lúc server đang xử lý form.
- Khi trình duyệt thực sự chuyển trang, `pagehide` sẽ dừng toàn bộ như trước.

### 3. Hủy request đúng theo từng nhóm

Bổ sung registry có `AbortController` cho request dùng chung:

- `abortRequest(key)` — hủy một request.
- `abortRequestsByPrefix(prefix)` — hủy nhóm request, ví dụ toàn bộ request phòng hiện tại.
- `abortAllRequests()` — hủy toàn bộ request khi rời trang.

Giữ tương thích với API JavaScript cũ:

- `requestOnce()` vẫn trả về Promise như trước.
- `fetchJsonOnce()` và `fetchTextOnce()` vẫn giữ nguyên cách gọi.
- Hỗ trợ registry cũ từng lưu Promise trực tiếp.

### 4. Thoát phòng vẫn dừng toàn bộ

- Bấm xác nhận Bỏ cuộc/Thoát phòng: dừng toàn bộ poller và request trước khi gửi form.
- Trang bị hủy, phòng đóng hoặc chuyển về sảnh: dừng toàn bộ.
- Sự kiện `pagehide`: dừng toàn bộ với lý do rõ ràng, không truyền nhầm Event object làm lý do dừng.

## File đã sửa

- `app.py`
  - Khoảng dòng 65: tăng phiên bản lên `Collap_V1.13.3lv3.2`.
  - Khoảng dòng 4247–4265: chuẩn hóa kiểm tra thành viên khi gửi chat.
- `static/js/pes_polling.js`
  - Khoảng dòng 16–95: registry request có khả năng hủy và chống request trùng.
  - Khoảng dòng 270–280: `stopAll()` hủy cả poller và request.
  - Khoảng dòng 325–370: truyền AbortSignal dùng chung cho `fetchJsonOnce()` và `fetchTextOnce()`.
  - Khoảng dòng 370–390: xuất các hàm hủy request.
- `templates/room_detail.html`
  - Khoảng dòng 249–286: tách dừng polling phòng và dừng toàn bộ trang.
  - Khoảng dòng 440–446: dừng toàn bộ khi `pagehide`.
  - Khoảng dòng 550–570: form thông thường chỉ dừng polling phòng.
  - Khoảng dòng 745–760: xác nhận thoát phòng vẫn dừng toàn bộ.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py`: đạt.
- `node --check static/js/pes_polling.js`: đạt.
- Parse `base.html` và `room_detail.html` bằng Jinja: đạt.
- Số route trước/sau: giữ nguyên 43 decorator route trong gói vá.
- `room_detail.html`: không có `location.reload()`.
- Chỉ có một tham chiếu endpoint trạng thái phòng.
- Mô phỏng hai lời gọi cùng request key: executor chỉ chạy một lần.
- Mô phỏng hủy request theo prefix: nhận đúng `AbortError`.
- Không có SQL Supabase mới.

## Cài đặt

Chép đè ba file code lên bản `Collap_V1.13.3lv3.1`. Không cần chạy SQL.
