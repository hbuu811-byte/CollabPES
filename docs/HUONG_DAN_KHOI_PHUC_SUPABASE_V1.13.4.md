# PES Arena V1.13.4 — Hướng dẫn khôi phục dữ liệu Supabase

## Trước khi khôi phục

1. Dừng tạo phòng, xác nhận kết quả và sửa trận.
2. Tạo một Backup mới của dữ liệu hiện tại.
3. Kiểm tra đúng Supabase Project đang được Vercel sử dụng.
4. Ưu tiên thử trước trên Supabase Test.

## Kiểm tra file

Vào `Admin > Backup dữ liệu`, chọn file ZIP/JSON và bấm `Kiểm tra và xem số bản ghi`.
Bước này chỉ đọc file, chưa ghi dữ liệu vào Supabase.

## Hai chế độ khôi phục

- **Gộp/cập nhật:** upsert theo khóa chính. Bản ghi cùng ID được cập nhật; bản ghi mới được thêm; dữ liệu khác vẫn giữ nguyên.
- **Thay thế toàn bộ:** xóa dữ liệu ở các bảng có trong Backup theo thứ tự an toàn, sau đó nạp lại. Dùng khi cần quay hệ thống về đúng thời điểm Backup.

## Xác nhận Production

Tài khoản sở hữu phải nhập mật khẩu hiện tại và cụm:

`KHOI PHUC DU LIEU`

## Sau khi khôi phục

1. Đăng xuất và đăng nhập lại.
2. Kiểm tra số người dùng, số trận, RP và bảng xếp hạng.
3. Kiểm tra một vài Profile và lịch sử trận.
4. Chỉ mở lại việc tạo/xác nhận trận khi dữ liệu đã đúng.
