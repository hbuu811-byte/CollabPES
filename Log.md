# Collap_V1.13.3lv1.1

- Ngày giờ: 19/07/2026 01:19, múi giờ Asia/Bangkok.
- Nhánh nền: `Collap_V1.13.3lv1`.
- Hình thức: gói vá, chỉ chứa các file cần chép đè.
- Không thay đổi công thức RP, dữ liệu trận đấu, Admin hoặc cấu trúc Supabase.

## Nội dung đã sửa

### 1. Sửa API chat trả về 403

- API đọc chat sảnh và chat phòng không còn trả 403 khi tính năng vừa bị tắt hoặc trang phòng đã hết quyền truy cập.
- Poller cũ nhận HTTP 204 cùng header `X-PES-Polling-Stop`, sau đó tự dừng.
- Thêm API gửi chat phòng bằng JSON: `/api/room/<room_id>/chat/send`.
- Gửi chat phòng không còn redirect rồi tải lại khung phòng.
- Giữ route form cũ làm phương án dự phòng khi JavaScript không hoạt động.

### 2. Chỉ giữ một bộ polling trạng thái phòng

- Chuyển polling `/state` vào registry chung của `pes_polling.js`.
- Dùng key duy nhất `room-state:<room_id>`.
- Khi khởi tạo lại cùng key, poller cũ bị dừng trước.
- Xóa bộ timer riêng `roomStateTimer`, `scheduleRoomStateCheck` và `runRoomStateCheck`.

### 3. Dừng polling cũ khi chuyển trang hoặc rời phòng

- `pagehide`: dừng toàn bộ poller khi rời hẳn trang; tạm dừng nếu trang được giữ trong BFCache.
- `pageshow`: khôi phục poller khi quay lại từ BFCache.
- `beforeunload`: dừng toàn bộ timer/listener lần cuối.
- Khi stop một poller, tháo cả listener `visibilitychange` và `online`.
- Khi phòng kết thúc, dừng đồng thời polling trạng thái và chat phòng.

### 4. Không reload toàn bộ trang phòng

- Không còn `location.reload()` trong `room_detail.html`.
- Thay đổi trạng thái chỉ thay `#roomLiveShell`.
- Quay đội, sẵn sàng, gửi kết quả và xác nhận tiếp tục dùng AJAX.
- Gửi chat phòng dùng API JSON và chỉ cập nhật danh sách chat.
- Chỉ điều hướng khỏi phòng khi phòng đã đóng hoặc người chơi thực sự rời phòng.

### 5. Ngăn `/api/invites/pending` chạy đồng thời

- Chỉ còn một vị trí gọi endpoint lời mời trong `base.html`.
- Thêm khóa toàn cục `PESNet.singleFlight("api:pending-invites", ...)`.
- Có khóa Promise dự phòng nếu `pes_polling.js` chưa tải được.
- Không tạo poller lời mời trong phòng, trang Lịch sử hoặc Hướng dẫn.

### 6. Khóa request đang chạy

- `/state`: khóa cục bộ `roomStateRequestInFlight` và khóa dùng chung `api:room-state:<room_id>`.
- Chat phòng: khóa đọc, khóa gửi và poller có key duy nhất.
- Chat sảnh: khóa đọc, kiểm tra chưa đọc và gửi tin.
- Lời mời: khóa request dùng chung cho mọi script.
- `PESNet.singleFlight()` trả lại Promise đang chạy thay vì tạo request mới.

### 7. Tăng cache static

- CSS/JS có version trong URL: cache 1 năm, `immutable`.
- Ảnh rank và ảnh giao diện: cache 30 ngày, cho phép revalidate trong 7 ngày.
- Static còn lại: giữ cache 7 ngày.
- Đồng bộ header trong Flask và `vercel.json`.

## Lỗi phụ phát hiện và xử lý

- Poller chat phòng trước đây không có key, có thể được tạo lại nhiều lần.
- `rebindRoomDynamicUi()` có thể gọi chat cùng lúc với poller; nay dùng chung một khóa request.
- Trang Chat và trang Lời mời có poller không key; nay đã có key rõ ràng.
- Trang Lời mời và `base.html` cùng dò phòng hoạt động; nay dùng cùng key `active-room`, nên chỉ còn một poller.
- `pes_polling.js` trước đây không tháo event listener khi dừng poller.
- Khi API chat trả 204, JavaScript cũ gọi `response.json()` và có thể sinh lỗi parse; nay đã xử lý riêng.

## File đã sửa và vị trí ước lượng

- `app.py`
  - Khoảng dòng 65: tăng `APP_VERSION`.
  - Khoảng dòng 1484–1502: cache CSS/JS và ảnh.
  - Khoảng dòng 3747–3785: response dừng polling trạng thái cũ.
  - Khoảng dòng 4100–4250: API chat sảnh/phòng và API gửi chat phòng.
- `static/js/pes_polling.js`
  - Toàn bộ file: registry singleton, khóa request, pause/resume/stop lifecycle và tháo listener.
- `templates/base.html`
  - Khoảng dòng 223–365: khóa heartbeat, active room và lời mời.
  - Khoảng dòng 430–650: khóa chat sảnh và quản lý poller khi đóng/mở.
  - Khoảng dòng 878–940: lịch polling theo từng trang.
- `templates/room_detail.html`
  - Khoảng dòng 339–347: form chat phòng AJAX.
  - Khoảng dòng 551–960: một poller `/state`, khóa request và không reload trang.
  - Khoảng dòng 960–1160: một poller chat, khóa đọc/gửi và tự dừng khi hết quyền.
- `templates/chat.html`
  - Khoảng dòng 61–90: poller chat có key và khóa request.
- `templates/invites.html`
  - Khoảng dòng 82–108: dùng chung key/khóa active room.
- `vercel.json`
  - Khoảng dòng 18–58: header cache theo loại static.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse toàn bộ template Jinja: đạt.
- `node --check` cho `pes_polling.js`, `session-timeout.js` và JavaScript trong 4 template đã sửa: đạt.
- Test runtime registry: hai poller cùng key chỉ còn một poller: đạt.
- Test runtime `singleFlight`: hai nơi gọi cùng request chỉ thực thi tác vụ mạng một lần: đạt.
- Kiểm tra tĩnh route trong `app.py`: không có route trùng.
- Kiểm tra `vercel.json`: JSON hợp lệ.
- Không còn `location.reload()` trong trang phòng.
- Không còn timer trạng thái phòng cũ.

## Giới hạn kiểm tra

Môi trường đóng gói hiện không cài thư viện Flask nên chưa chạy được full import Flask và test kết nối Supabase thực tế. Không có SQL mới cần chạy.
