# Collap_V1.13.3lv1.4

- Ngày giờ: 19/07/2026 23:19, múi giờ Asia/Bangkok.
- Bản nền: `Collap_V1.13.3lv1.3`.
- Phạm vi: cập nhật phòng theo sự kiện và chỉ thay các khối giao diện đã đổi.
- Không thay đổi: RP, phạt bỏ cuộc, lịch sử bỏ cuộc, modal thoát phòng, giao diện lịch sử tỷ số, Admin, Supabase hoặc cache static đã cấu hình ở nhánh trước.

## Nội dung sửa

### 1. Không dựng lại toàn bộ phòng

- Bỏ cơ chế thay toàn bộ `#roomLiveShell` khi trạng thái đổi.
- Chia phần động thành 8 fragment độc lập:
  - sự kiện/danh hiệu;
  - thanh thông tin trên;
  - thẻ chủ phòng;
  - khu vực giữa và tỷ số;
  - thẻ khách;
  - thông tin phòng;
  - lịch sử tỷ số;
  - điều khiển phòng.
- Client so sánh HTML của từng fragment và chỉ thay fragment có nội dung khác.
- Fragment không đổi giữ nguyên DOM, ảnh, focus, input, animation và listener.

### 2. Chỉ trả dữ liệu khi có sự kiện

- `/api/room/<id>/state` tiếp tục trả HTTP 204 khi khóa sự kiện không đổi.
- Khóa trạng thái bổ sung `updated_at` và `match_id`, sau đó băm SHA-256 để ổn định và gọn hơn.
- Sau thao tác AJAX thành công, dùng ngay dữ liệu trả về; bỏ request `/state` lặp lại sau 500 ms.
- Khi tab bị ẩn, dừng polling phòng; quay lại tab mới kiểm tra ngay một lần.

### 3. Partial response

- Route `/room/<id>` hỗ trợ header `X-PES-Room-Partial: 1`.
- Request AJAX chỉ nhận phần HTML động của phòng dưới dạng JSON, không gửi lại `base.html`, menu hoặc link CSS/JS.
- Flash lỗi/cảnh báo quan trọng vẫn được trả trong JSON để hiển thị bằng modal PES Arena.
- Có fallback đọc HTML đầy đủ nếu trình duyệt không giữ header qua redirect, tránh thao tác thành công nhưng giao diện báo lỗi.

### 4. Chat chỉ cập nhật khi có tin mới

- API chat tạo `chat_key` từ danh sách tin mới nhất.
- Client gửi `since=<chat_key>`.
- Không có tin mới: API trả HTTP 204 và giữ nguyên DOM chat.
- Có tin mới: chỉ khi đó mới gửi danh sách và render chat.
- Tách khóa server và khóa render để không tạo vòng tải lặp.

### 5. Cache

- Giữ nguyên cấu hình đã có:
  - CSS/JS: 1 năm, `immutable`;
  - ảnh rank và ảnh giao diện: 30 ngày;
  - URL CSS/JS gắn `APP_VERSION`.
- Phiên bản mới chỉ tải static một lần; các cập nhật phòng không tải lại CSS/JS/ảnh không đổi.

## File đã sửa

- `app.py`
  - Khoảng dòng 65: tăng phiên bản.
  - Khoảng dòng 3737–3761: khóa sự kiện phòng ổn định.
  - Khoảng dòng 4176–4200: chat trả 204 khi không đổi.
- `modules/room_access_routes.py`
  - Khoảng dòng 3–5: import flash reader.
  - Khoảng dòng 159–207: partial JSON response của phòng.
- `templates/room_detail.html`
  - Khoảng dòng 4–497: đánh dấu 8 fragment động.
  - Khoảng dòng 754–1050: so sánh và chỉ thay fragment đã đổi.
  - Khoảng dòng 1086–1280: chat dùng `since/chat_key`, không render khi không đổi.

## Kiểm tra

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse 24 template Jinja: đạt.
- Kiểm tra cú pháp JavaScript bằng Node.js: đạt.
- Render thử phòng và xác nhận đủ đúng 8 fragment duy nhất: đạt.
- `location.reload()` trong phòng: 0.
- Tham chiếu cơ chế thay toàn bộ `roomLiveShell`: 0.
- Không thêm route mới, không cần SQL Supabase.

## Cài đặt

Chép đè 3 file code trong gói này lên `Collap_V1.13.3lv1.3`. `Log.md` chỉ dùng để tra cứu.
