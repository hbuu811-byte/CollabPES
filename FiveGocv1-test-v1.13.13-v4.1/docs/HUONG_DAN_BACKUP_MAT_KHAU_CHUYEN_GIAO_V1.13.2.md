# PES Arena V1.13.2 — Backup, mật khẩu Test và chuyển giao

## 1. Backup dữ liệu

Vào **Admin → Backup dữ liệu**, nhập `SAO LUU DU LIEU` khi chạy trên Production và bấm **Tạo và tải Backup ZIP**.

Backup chỉ đọc dữ liệu, không thay đổi database. File ZIP chứa JSON của các bảng quan trọng. File có thể chứa hash mật khẩu và lịch sử hoạt động, vì vậy không đưa lên GitHub và không gửi công khai.

Nên backup trước khi:

- Tính lại RP toàn hệ thống.
- Import tài khoản hàng loạt.
- Sửa hoặc xóa nhiều trận.
- Chuyển giao quyền sở hữu.
- Chạy migration lớn.

## 2. Dùng mật khẩu `1` để test

Chỉ bật ở Vercel Project Test, với Supabase Test riêng:

```env
APP_ENV=test
PES_ARENA_TEST_MODE=true
DATABASE_SAFETY_TOKEN=PES_ARENA_TEST_DATABASE
ALLOW_SIMPLE_TEST_PASSWORDS=true
```

Khi đủ bốn điều kiện, tài khoản người chơi và Admin có thể dùng mật khẩu `1`. Production vẫn bắt buộc tối thiểu 6 ký tự ngay cả khi cấu hình bị thiếu hoặc đặt sai một phần.

## 3. Đổi mật khẩu

Mở **Hồ sơ cá nhân → Điều khiển hồ sơ**. Chỉ nhập:

1. Mật khẩu hiện tại.
2. Mật khẩu mới.

Không cần nhập lại mật khẩu mới lần hai.

## 4. Chuyển giao quyền sở hữu

Vào **Admin → Tổng quan → Đội ngũ quản trị → Chuyển giao quyền sở hữu**.

- Chọn tài khoản nhận.
- Nhập mật khẩu hiện tại của chủ sở hữu.
- Nhập `CHUYEN GIAO`.
- Sau khi hoàn tất, hệ thống đăng xuất.
- Tài khoản nhận trở thành chủ sở hữu; tài khoản cũ trở thành Admin.
