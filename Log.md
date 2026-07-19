# Collap_V1.13.3lv3.4 — Cập nhật phòng theo sự kiện

- Ngày giờ: 19/07/2026, múi giờ Asia/Bangkok.
- Bản nền bắt buộc: `Collap_V1.13.3lv3.3`.
- Loại gói: trình vá an toàn, chỉ sửa file liên quan.
- SQL Supabase: không cần.

## Mục tiêu

- Không reload toàn bộ trang sau thao tác trong phòng.
- Không thay toàn bộ `#roomLiveContent` khi chỉ một nội dung nhỏ đổi.
- Ưu tiên cập nhật ngay sau sự kiện người dùng.
- Giữ cache HTML hiện tại và không tải lại CSS, JavaScript hoặc ảnh không đổi.
- Giảm polling thường xuyên nhưng vẫn có kiểm tra dự phòng để hai máy không bị lệch trạng thái khi mất tín hiệu.

## Nội dung sửa

### 1. Thao tác phòng bằng AJAX

Các thao tác Sẵn sàng, Hủy sẵn sàng, quay đội, gửi kết quả, xác nhận, tranh chấp, đá tiếp và gửi chat không còn đi theo redirect để tải lại toàn trang.

Backend nhận header `X-PES-Room-Action: 1` và trả JSON gồm:

- HTML động mới nhất của phòng;
- `state_key` mới;
- thông báo lỗi/cảnh báo cần hiển thị;
- URL chuyển trang nếu người chơi thật sự rời phòng.

### 2. Chỉ vá node giao diện thay đổi

Client không còn dùng:

```text
target.innerHTML = html
```

Thay vào đó, bộ vá DOM so sánh node, thuộc tính và nội dung chữ. Chỉ node khác mới được cập nhật. Các phần không đổi giữ nguyên:

- ảnh đã tải;
- focus và vị trí con trỏ;
- tỷ số đang nhập;
- trạng thái mở của khung chi tiết;
- animation và vị trí cuộn.

### 3. Cache phía trình duyệt

- HTML động gần nhất lưu trong `sessionStorage` theo ID phòng.
- `state_key` gần nhất cũng được lưu riêng.
- Nếu server trả cùng HTML, không vá DOM lần nữa.
- CSS/JS/ảnh tiếp tục dùng cache dài của nhánh `lv3.1`–`lv3.3`.

### 4. Event-first

Cập nhật ngay khi có:

- thao tác phòng thành công;
- tab trở lại hiển thị;
- cửa sổ được focus;
- kết nối mạng trở lại;
- trang được phục hồi từ BFCache;
- sự kiện từ tab khác cùng phòng qua `BroadcastChannel`.

Không còn poller `/state` của `PESNet` chạy liên tục.

### 5. Kiểm tra dự phòng

Hạ tầng hiện tại chưa bật Supabase Realtime trực tiếp ở trình duyệt. Để tránh máy khách không nhận được thao tác của đối thủ khi mất sự kiện, giữ một watchdog nhẹ:

| Trạng thái | Chu kỳ dự phòng |
|---|---:|
| Chờ xác nhận kết quả | 8–15 giây |
| Chờ sẵn sàng / Đá tiếp | 15 giây |
| Đang thi đấu | 60 giây |
| Trạng thái khác | 30 giây |

Tab bị ẩn không gửi request.

### 6. Chat theo thay đổi

- Client gửi `since=<chat_key>`.
- Không có tin mới: API trả HTTP 204, không gửi danh sách và không render lại chat.
- Có tin mới: chỉ cập nhật khung chat.
- Chat kiểm tra ngay sau thao tác, khi tab hiện lại và có watchdog 60 giây.

## File được sửa sau khi chạy

| File | Nội dung |
|---|---|
| `app.py` | Version; JSON response cho thao tác phòng; chat `since/chat_key` |
| `templates/room_detail.html` | AJAX form; event sync; cache; vá DOM theo node; watchdog nhẹ |

## Không thay đổi

- Không sửa RP, công thức Rank hoặc phạt bỏ cuộc.
- Không sửa lịch sử trận và lịch sử tỷ số trong phòng.
- Không sửa Admin, CSS, `vercel.json` hoặc cấu trúc Supabase.
- Không thêm thư viện JavaScript bên ngoài.

## Cài đặt

1. Chép ba file trong ZIP vào thư mục gốc dự án `Collap_V1.13.3lv3.3`.
2. Nhấp đúp `APPLY_Collap_V1.13.3lv3.4.bat`.
3. Commit đúng:
   - `app.py`;
   - `templates/room_detail.html`.
4. Không commit `.collap_v1_13_3lv3_4_backup`.
