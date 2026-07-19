# Collap_V1.13.3lv3.1

- Ngày giờ: 19/07/2026 01:22
- Múi giờ: Asia/Bangkok
- Bản nền: Collap_V1.13.3lv3 (mã nguồn hiện tại là Collap_V1.13.3l)
- Phạm vi: sửa API chat, hợp nhất polling, khóa request và tăng cache file tĩnh.
- Không thay đổi: công thức RP, luồng xác nhận kết quả, lịch sử trận, giao diện tỷ số phòng và cấu trúc Supabase.

## Các lỗi phát hiện

1. API chat trả 403 khi Admin vừa tắt chat phòng hoặc khi `guest_user_id` vừa bị xóa trong lúc trang cũ chưa kịp chuyển hướng.
2. Kiểm tra quyền ở `/state`, `/view` và chat so sánh ID trực tiếp; có thể nhận sai khi một phía là số và phía còn lại là chuỗi.
3. Poller cũ bị `stop()` nhưng vẫn giữ listener `visibilitychange`, `online`, `pagehide`, `pageshow` và `beforeunload`.
4. Poller không có `key` không được lưu trong registry nên không thể dừng toàn bộ bằng một lệnh.
5. Khi hai script cùng tạo một poller có cùng key trong cùng nhịp chạy, task immediate của poller cũ vẫn có thể lọt qua hàng đợi microtask.
6. `/api/invites/pending` chỉ có khóa ở cấp poller; một lời gọi trực tiếp khác vẫn có thể tạo request thứ hai.
7. Chat và `/state` chưa có khóa dùng chung theo endpoint, nên một script phụ vẫn có thể chạy chồng với poller chính.
8. Ảnh giao diện và ảnh rank mới cache 30 ngày.

## Nội dung sửa

### API chat

- Khi chat phòng bị tắt: trả HTTP 200 với `disabled=true`, không lặp 403.
- Khi phòng vừa đóng hoặc người chơi vừa rời: trả HTTP 200 với `closed=true` và danh sách rỗng.
- Phòng đang hoạt động vẫn giữ kiểm tra quyền; tài khoản lạ không được đọc tin nhắn.
- API chat chỉ đọc 4 cột phòng cần thiết thay vì gọi `get_room()` đầy đủ.
- Client tự dừng poller chat khi nhận `disabled`, `closed`, 401, 403 hoặc 404.

### Polling phòng

- Chỉ giữ một poller `room-state:<room_id>`.
- Trước khi tạo poller trạng thái/chat mới, dừng mọi poller cùng nhóm cũ.
- Không dùng `window.location.reload()` để đồng bộ phòng.
- Khi trạng thái thay đổi, chỉ thay `#roomLiveContent`.
- Khi rời trang, gửi form phòng, xác nhận bỏ cuộc hoặc chuyển về sảnh: dừng toàn bộ poller và hủy request đang chạy.
- Khi trang nằm trong Back/Forward Cache: tạm hủy request và chạy lại khi trang được phục hồi.

### Khóa request

- Thêm registry `requestOnce`.
- `/state`: khóa `request:room-state:<room_id>`.
- Chat phòng: khóa `request:room-chat:<room_id>`.
- Lời mời: khóa `request:pending-invites`.
- Request cùng khóa dùng chung một Promise, không tạo kết nối thứ hai.
- Poller cùng key thay thế poller cũ mà không để task immediate cũ chạy lọt.

### Dọn polling cũ

- Theo dõi cả poller có key và không có key.
- `stopAll()` dừng toàn bộ poller.
- `stopByPrefix()` dừng một nhóm poller.
- `stop()` xóa timer, abort request và gỡ toàn bộ event listener.
- `hasPoller()` ngăn script thứ hai tạo lại polling lời mời.

### Cache

- CSS/JS: 1 năm, immutable.
- Font: 1 năm, immutable.
- Ảnh PNG/JPG/JPEG/WebP/GIF/SVG/ICO, bao gồm ảnh rank và giao diện: 180 ngày.
- `stale-while-revalidate`: 7 ngày.
- API và heartbeat tiếp tục `no-store`.

## File đã sửa

- `app.py`
  - khoảng dòng 65: tăng phiên bản.
  - khoảng dòng 1484–1496: cache ảnh 180 ngày.
  - khoảng dòng 3800–3818: kiểm tra ID an toàn cho `/state`.
  - khoảng dòng 4200–4250: sửa API chat 403 và giảm dữ liệu truy vấn.
- `modules/room_access_routes.py`
  - khoảng dòng 173–193: kiểm tra ID an toàn cho HTML động của phòng.
- `templates/base.html`
  - khoảng dòng 318–375: khóa request lời mời.
  - khoảng dòng 830–840: chỉ tạo một poller lời mời.
- `templates/room_detail.html`
  - khoảng dòng 249–430: dừng polling cũ, khóa `/state`, xử lý lỗi quyền và không reload trang.
  - khoảng dòng 477–535: khóa chat và tự dừng khi phòng/chat đóng.
  - khoảng dòng 537–555, 730–745: dừng toàn bộ polling trước khi gửi form hoặc rời phòng.
- `static/js/pes_polling.js`
  - toàn file: singleton poller, request lock, stopAll, stopByPrefix, dọn listener và hỗ trợ BFCache.
- `vercel.json`
  - phần headers: tăng cache ảnh và bổ sung cache font.

## Kiểm tra

- Python compile `app.py` và module sửa: đạt.
- Parse 25 template Jinja: đạt.
- Node `--check` cho `pes_polling.js`: đạt.
- Node `--check` cho 12 khối JavaScript trong `base.html` và `room_detail.html`: đạt sau khi thay biểu thức Jinja bằng dữ liệu kiểm tra.
- Mô phỏng hai poller cùng key: chỉ task mới chạy 1 lần.
- Mô phỏng gọi request cùng key: chỉ tạo 1 request.
- Mô phỏng gọi `runNow()` liên tục: số request chạy đồng thời tối đa là 1.
- Mô phỏng `stopAll()`: gỡ toàn bộ 10 listener thử nghiệm, registry còn 0 poller.
- Số route trước và sau: 69 decorator route, không thêm hoặc mất route.
- Trang phòng: 1 tham chiếu `/state`, 1 key poller trạng thái, 0 `location.reload()`.
- Lời mời: 1 endpoint, 1 key request lock.
- Không cần chạy SQL Supabase.

## Cài đặt

Chép đè các file trong gói này lên nhánh `Collap_V1.13.3lv3`.
