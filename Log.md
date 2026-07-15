# PES 2026 WEB — V1.10.69 Hybrid Room Controls

## Nâng cấp
- Giữ nguyên toàn bộ bản V1.10.68 đã hoạt động ổn định.
- Đưa nút **Mời Đấu** vào chính giữa sân đấu khi chủ phòng đang chờ đối thủ.
- Khi khách vào phòng: hiển thị **Sẵn Sàng / Hủy Sẵn Sàng** và **Thoát Phòng** ở giữa sân đấu.
- Sau khi trận hoàn thành: cả chủ và khách đều thấy **Đá Tiếp** và **Thoát Phòng** ở giữa sân đấu.
- Loại bỏ các nút trùng lặp ở khu vực Điều khiển phòng.
- Thêm màn phủ tối khi gửi thao tác hoặc khi trạng thái phòng tự tải lại, giúp không còn cảm giác nháy trắng.
- Không thay đổi cơ chế backend, RP, random đội hoặc xác nhận kết quả.

# PES 2026 WEB — V1.10.68 Hybrid UI Fix

## Nền tảng

- Tiếp tục dùng V1.10.65 Hybrid làm nền backend nhẹ.
- Giữ giao diện và bộ ảnh tương thích với V1.10.64c.
- Không bổ sung polling dày, HTMX room refresh hoặc state-fragment.

## Sửa lỗi V1.10.68

- Bổ sung `WIN_STREAK_TITLES`.
- Khôi phục `get_streak_title()` và `get_streak_badge()` bị thiếu khi ghép Hybrid.
- Sửa lỗi `NameError: get_streak_badge is not defined` tại `/players`, `/profile/<id>` và các API gọi `list_rooms()`.
- Bổ sung `get_league_logo_path()` tương thích với cơ chế logo giải mới của V1.10.64c.
- Ngăn lỗi tiếp theo khi phòng đấu có CLB và logo giải.

## Cách cập nhật

1. Sao lưu dự án hiện tại.
2. Chép các file của bản này vào dự án V1.10.66 và chọn ghi đè.
3. Giữ nguyên toàn bộ ảnh trong `static` của V1.10.64c.
4. Commit lên nhánh test trước.
5. Kiểm tra `/players`, hồ sơ người chơi, `/api/active-room`, Quay quân, Xác nhận và Đá tiếp.


## V1.10.68 Hybrid UI – Submit Result Fix
- Khôi phục hàm `is_ranked_room()` bị thiếu sau khi ghép Hybrid.
- Sửa lỗi 500 khi chủ phòng gửi kết quả.
- Sửa luồng xác nhận kết quả dùng chung kiểm tra chế độ Rank.
- Giữ nguyên cơ chế phòng đấu nhẹ của V1.10.15; không thêm polling/fragment mới.
