# Collap_V1.13.3lv2.4

- Ngày giờ: 19/07/2026 22:10, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3lv2.3.
- Phạm vi: sửa luồng đồng bộ tín hiệu từ chủ phòng sang máy khách; không thay đổi RP, lịch sử, phạt bỏ cuộc, modal hoặc công thức trận đấu.

## Nguyên nhân xác định

1. API `/api/room/<room_id>/state` đang làm quá nhiều việc trong một request: đọc phòng, làm giàu dữ liệu, truy vấn lịch sử và render fragment.
2. Khi phần truy vấn lịch sử/render chậm hoặc lỗi trên Vercel, máy khách không nhận được cả tín hiệu trạng thái dù Supabase đã cập nhật.
3. API `/api/invites/pending` biến lỗi truy vấn thành HTTP 200 với `invites: []`, khiến giao diện hiểu nhầm là không có lời mời.
4. Polling chỉ khởi động qua `DOMContentLoaded`; bổ sung bootstrap an toàn cho BFCache/trường hợp script được thực thi khi DOM đã sẵn sàng.

## Nội dung sửa

### Đồng bộ phòng hai bước

- `/api/room/<room_id>/state` chỉ đọc một dòng `match_rooms`, tính `state_key` và trả JSON rất nhẹ.
- Không render Jinja và không truy vấn lịch sử trong request polling thường xuyên.
- Khi `state_key` thay đổi, máy khách mới gọi `/api/room/<room_id>/fragment` một lần để lấy giao diện mới.
- Nếu tải fragment lỗi, máy khách không cập nhật `state_key`; chu kỳ sau tự thử lại mà không cần F5.
- Không retry dồn dập, giữ chu kỳ polling bình thường để bảo toàn lượng request thấp.
- Không reload toàn bộ trang.

### Lời mời

- Truy vấn trực tiếp vẫn là đường chính.
- Nếu truy vấn trực tiếp lỗi, fallback về helper lời mời cũ và lọc đúng người nhận.
- Nếu cả hai truy vấn lỗi, API trả HTTP 503 thay vì giả danh sách rỗng.
- Popup không bị đóng khi server gặp lỗi tạm thời.
- Có fallback lấy thông tin người gửi; lời mời vẫn hiển thị dù dữ liệu huy hiệu/avatar tạm lỗi.

### Khởi động poller

- Polling phòng và lời mời khởi động ngay nếu DOM đã sẵn sàng.
- Hỗ trợ khởi động lại khi trang được phục hồi từ BFCache.
- Vẫn chỉ giữ một timer trạng thái phòng và một poller lời mời.

## File đã sửa

- `app.py`
  - Khoảng dòng 65: tăng phiên bản.
  - Khoảng dòng 3060–3120: cho phép fragment realtime bỏ fallback tải toàn bộ lịch sử.
  - Khoảng dòng 3644–3745: sửa API lời mời với fallback an toàn và HTTP lỗi đúng.
  - Khoảng dòng 3802–3925: tách snapshot `/state` và fragment `/fragment`.
- `templates/room_detail.html`
  - Khoảng dòng 250–590: thêm khóa request fragment, cơ chế tải fragment khi state đổi và bootstrap an toàn.
- `templates/base.html`
  - Khoảng dòng 337–380: không ẩn popup khi API báo lỗi.
  - Khoảng dòng 953–965: bootstrap polling lời mời ngay/BFCache.

## Kiểm tra

- Biên dịch `app.py` và toàn bộ module Python: đạt.
- Parse 25 template Jinja: đạt.
- Render thử trang phòng và kiểm tra 10 khối JavaScript nội tuyến bằng Node: đạt.
- Không có `location.reload()` trong trang phòng.
- Chỉ một điểm gọi `/state` trong trang phòng.
- Chỉ một điểm gọi `/api/invites/pending` trong template.
- Route mới: `/api/room/<room_id>/fragment`.
- Không cần chạy SQL Supabase.

## Cài đặt

Chép đè ba file code lên Collap_V1.13.3lv2.3. Không áp dụng lên các nhánh song song khác.
