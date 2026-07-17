# V1.13.10 – Trở lại phòng và lịch sử đối đầu

## Nút Trở Lại Phòng Đấu
Mở Hồ sơ cá nhân → Điều khiển hồ sơ. Nút chỉ xuất hiện khi tài khoản đang tham gia một phòng hoạt động.

## Lịch sử đối đầu trong phòng
Mở phòng đấu → Điều khiển phòng. Hệ thống chỉ đếm trận `confirmed` giữa đúng hai thành viên, có thời gian tạo từ `rooms.created_at` của phòng hiện tại trở đi. Các trận cũ trước khi mở phòng, trận hủy và trận chưa xác nhận không được tính.

## Cài đặt
Chép đè file, Commit, Push và Redeploy Vercel. Không cần SQL Supabase.
