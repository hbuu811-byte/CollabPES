# Collap_V1.13.3l — Tối ưu phòng đấu và polling

- **Ngày giờ:** 19/07/2026 00:12, múi giờ Asia/Bangkok.
- **Bản nền:** `Collap_V1.13.3k`.
- **Loại gói:** chỉ chứa các file cần chép đè.
- **SQL Supabase:** không cần chạy.
- **Mục tiêu:** giảm lag/delay phía khách, giảm request trùng, giữ nguyên dữ liệu đang nhập và không làm mất các nâng cấp từ `Collap_V1.13.2` đến `Collap_V1.13.3k`.

## Kết quả theo 10 mục yêu cầu

| Thứ tự | Yêu cầu | Xử lý trong V1.13.3l |
|---:|---|---|
| 1 | Sửa việc trang phòng reload | Bỏ `window.location.reload()` khỏi trang phòng. Khi trạng thái thay đổi, chỉ tải HTML động và thay phần `#roomLiveContent`; thanh menu, modal và toàn trang không bị tải lại. |
| 2 | Gộp polling `/state` còn một vòng | Trang phòng chỉ còn một poller có khóa duy nhất `room-state:<room_id>` và một URL `/api/room/<id>/state`. |
| 3 | Ngăn request trạng thái chạy chồng | `PESNet.createPoller()` dùng `inFlight`, `AbortController`, timeout và hàng đợi tối đa một lần chạy lại. Poller trùng khóa sẽ tự dừng poller cũ. |
| 4 | Không ghi đè ô tỷ số khi đang nhập | Trước khi cập nhật phần phòng, hệ thống lưu value/checked/focus/vị trí con trỏ của form; sau đó phục hồi. Riêng tỷ số còn được lưu nháp trong `sessionStorage`. Polling vẫn tiếp tục thay vì bị dừng toàn bộ khi đang nhập. |
| 5 | Giãn session activity | Bản nền thực tế đã là **300 giây**, tốt hơn mức 60 giây về số request nên giữ 300 giây. Bổ sung khóa `activitySyncInFlight` và không gửi khi tab ẩn. |
| 6 | Giãn lời mời | Lời mời kiểm tra mỗi **15 giây** ngoài phòng và **20 giây** trong phòng; dừng khi tab ẩn. |
| 7 | Giãn heartbeat | Heartbeat đặt **45 giây**, phù hợp mốc xác định online 90 giây; dừng khi tab ẩn. |
| 8 | Giãn thông báo | Thông báo hệ thống kiểm tra mỗi **60 giây**; chuông thông báo cá nhân không có vòng polling riêng. |
| 9 | Dừng polling khi tab ẩn | Poller trạng thái phòng, chat phòng, heartbeat, lời mời, active-room, chat sảnh, thông báo hệ thống và online count đều không gửi request khi tab ẩn. Request đang chạy được hủy bằng `AbortController`. |
| 10 | Cache CSS, JS, ảnh | CSS/JS gắn `?v=APP_VERSION` và cache immutable 1 năm. Ảnh cache 30 ngày kèm stale-while-revalidate. API và heartbeat giữ `no-store`. |

## Thay đổi kỹ thuật chính

### 1. Phòng đấu cập nhật từng phần, không reload

- Thêm `templates/_room_live_content.html` chứa phần giao diện thay đổi theo trạng thái phòng.
- `templates/room_detail.html` giữ phần khung, modal và JavaScript cố định.
- Thêm endpoint `GET /api/room/<room_id>/view` để trả HTML động khi `state_key` thật sự thay đổi.
- API `/state` vẫn trả HTTP 204 khi không có thay đổi.

### 2. `/state` nhẹ hơn

- Thêm `get_room_state_snapshot()` chỉ đọc các cột cần thiết từ `match_rooms`.
- Không còn chạy `get_room()` đầy đủ ở mỗi vòng polling, do đó không truy vấn lại users, rank, đội bóng, lịch sử và tranh chấp mỗi lần.
- Chỉ làm giàu dữ liệu khi thời hạn phòng thực sự hết hạn và cần xử lý nghiệp vụ.

### 3. Polling động theo giai đoạn

| Trạng thái phòng | Chủ phòng | Khách |
|---|---:|---:|
| Chờ sẵn sàng | 3 giây | 3 giây |
| Đang thi đấu xếp hạng | 6 giây | 2,5 giây |
| Chờ xác nhận kết quả | 3,5 giây | 1,5 giây |
| Giao hữu | 6 giây | 6 giây |
| Đã xác nhận | 4 giây | 4 giây |
| Trạng thái khác | 7 giây | 7 giây |

Khách được kiểm tra nhanh hơn ở hai giai đoạn cần nhận thay đổi từ chủ phòng, còn chủ phòng giảm request thừa.

## File đã sửa

| File | Khoảng dòng | Nội dung |
|---|---:|---|
| `app.py` | khoảng 65; 1480–1500; 2626–2665; 3777–3838 | Tăng phiên bản, cache theo loại file, snapshot `/state` nhẹ, trả 204 khi không đổi. |
| `modules/room_access_routes.py` | khoảng 141–193 | Gom context phòng và thêm endpoint HTML động `/api/room/<room_id>/view`. |
| `templates/room_detail.html` | toàn bộ phần nội dung động và khoảng 85–455 | Bỏ reload, một poller `/state`, cập nhật từng phần, bảo toàn form/tỷ số, polling động, dừng khi ẩn. |
| `templates/_room_live_content.html` | file mới | Phần HTML phòng được cập nhật khi trạng thái đổi. |
| `templates/base.html` | khoảng 9–23; 798–850 | Version hóa static; heartbeat 45 giây; lời mời 15/20 giây; thông báo 60 giây; dừng polling khi ẩn. |
| `static/js/pes_polling.js` | toàn file | Singleton poller, chống chạy chồng, abort, timeout, dynamic interval và xử lý 204/304. |
| `static/js/session-timeout.js` | khoảng 70–105 | Khóa request activity, không gửi chồng hoặc gửi khi tab ẩn. |
| `static/style.css` | cuối nhóm giao diện phòng | Giữ layout sau khi thêm wrapper HTML động. |
| `vercel.json` | phần `headers` | Cache CSS/JS/ảnh trên Vercel. |

## Kiểm tra đã thực hiện

- `python -m py_compile app.py modules/*.py`: đạt.
- RP Engine `RP_V1.12.0`: đạt.
- Parse 25 template Jinja: đạt.
- Kiểm tra cú pháp `pes_polling.js`, `session-timeout.js` và 4 khối JavaScript trong trang phòng: đạt.
- So sánh route với `Collap_V1.13.3k`: không mất route; chỉ thêm `/api/room/<room_id>/view`.
- Route/HTTP method trùng: không phát hiện.
- Kiểm tra poller mô phỏng: số request chạy đồng thời tối đa bằng 1.
- Kiểm tra trang phòng: không còn `window.location.reload()` và chỉ còn một tham chiếu `/state`.
- Không có `.pyc`, `__pycache__` hoặc file backup trong gói.
- Chưa thể chạy full import Flask trong môi trường kiểm tra vì môi trường này không cài package `flask`; đã kiểm tra bằng compile, AST route, Jinja và JavaScript thay thế.

## Cách áp dụng

1. Dùng dự án đã áp dụng đến `Collap_V1.13.3k`.
2. Giải nén `Collap_V1.13.3l.zip`.
3. Chép đè đúng các file trong gói vào repository.
4. Commit và deploy lên nhánh test.
5. Test bằng hai trình duyệt: chờ sẵn sàng, quay đội, nhập tỷ số, xác nhận, đá tiếp và chuyển tab ẩn/hiện.
