# Collap_V1.13.3lv2.5

- Ngày: 20/07/2026
- Múi giờ: Asia/Bangkok
- Bản nền: Collap_V1.13.3lv2.4
- Phạm vi: chỉ sửa polling lời mời; không sửa API tạo lời mời, phòng đấu, RP, lịch sử hoặc database.

## Nguyên nhân regression

Từ Collap_V1.13.3lv2.1, poller lời mời bị dừng vĩnh viễn sau một response 401, 403 hoặc HTML bất thường. `configureInvitePolling()` cũng luôn dừng poller và hủy request đang chạy trước khi tạo lại. Khi PESNet vẫn tồn tại nhưng poller đã chết, timer dự phòng của lv2.3/lv2.4 không được kích hoạt.

## Nội dung sửa

- Không dừng polling vĩnh viễn sau lỗi 401/403/503, HTML bất thường hoặc lỗi mạng tạm thời.
- Lỗi tạm thời chờ đúng chu kỳ hiện tại rồi thử lại; không tăng tần suất request.
- Chỉ ghi cảnh báo console sau 3 lỗi liên tiếp và tối đa một lần mỗi 60 giây.
- `configureInvitePolling()` giữ nguyên poller/request nếu cấu hình trang chưa đổi.
- Không còn tự abort `/api/invites/pending` mỗi lần cấu hình lại cùng trang.
- Thêm watchdog không phát sinh API request; chỉ kiểm tra poller đã bị stop hay chưa.
- Watchdog khôi phục poller kể cả khi `PESNet` vẫn tồn tại.
- Timer dự phòng chỉ hoạt động khi `PESNet` chưa tải được; không chạy đồng thời với poller chuẩn.
- Khi tab hiện lại, mạng online lại hoặc trang phục hồi từ BFCache: gọi kiểm tra ngay một lần.
- Khi thực sự rời trang: dừng poller và hủy request.
- `pes_polling.js` bổ sung `isStopped()` và `isPaused()` để phân biệt poller chết với poller chỉ tạm dừng khi tab ẩn.

## File sửa

- `app.py` khoảng dòng 65: tăng phiên bản.
- `templates/base.html` khoảng dòng 331–430 và 867–990: sửa request và bộ điều khiển polling lời mời.
- `static/js/pes_polling.js` khoảng dòng 150–160: bổ sung trạng thái poller.

## Cài đặt

Chép đè ba file vào Collap_V1.13.3lv2.4. Không cần chạy SQL Supabase.
