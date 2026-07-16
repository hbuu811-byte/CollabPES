# PES 2026 WEB V1.12.1

## Thay đổi

- Chuyển khối nhập kết quả trận đấu vào khu vực trung tâm, ngay dưới ảnh VS.
- Làm đậm tiêu đề Kết quả trận đấu, Sân Nhà, Sân Khách và nút Gửi Kết Quả.
- Ép các cặp nút Sẵn Sàng/Hủy Sẵn Sàng, Đá Tiếp và Thoát Phòng nằm cạnh nhau trên một hàng.
- Giữ trạng thái Đã Chọn Đá Tiếp khi người chơi đã chọn.
- Tắt thông báo Smart Random sau khi quay đội.
- Tắt thông báo xác nhận điểm Chủ phòng/Khách sau khi xác nhận kết quả.
- Giữ nguyên công thức RP và toàn bộ chức năng khác của V1.12.0.

## File thay đổi

- `app.py`: cập nhật phiên bản và bỏ hai thông báo thừa.
- `templates/room_detail.html`: chuyển form kết quả vào giữa phòng và giữ logic nút theo vai trò/trạng thái.
- `static/style.css`: bố trí nút một hàng, định dạng form kết quả mới.

## Cài đặt

1. Giải nén ZIP.
2. Sao chép toàn bộ file vào thư mục gốc repository.
3. Chọn ghi đè file trùng tên.
4. Commit và push lên branch thử nghiệm.
5. Deploy Vercel và kiểm tra bằng hai tài khoản.

Không cần chạy SQL và không thay đổi cấu trúc Supabase.
