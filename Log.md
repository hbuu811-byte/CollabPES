# PES 2026 WEB — V1.10.67 Hybrid UI Fix

## Nền tảng

- Tiếp tục dùng V1.10.65 Hybrid làm nền backend nhẹ.
- Giữ giao diện và bộ ảnh tương thích với V1.10.64c.
- Không bổ sung polling dày, HTMX room refresh hoặc state-fragment.

## Sửa lỗi V1.10.67

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
