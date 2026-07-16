# PES 2026 WEB V1.12.0

## Thay đổi

- Phiên bản dưới logo chỉ hiển thị `V1.12.0`, bỏ chữ `CHAMPIONSHIP`.
- Bỏ khung "Trạng thái hệ thống" ở cuối thanh menu trái.
- Bỏ dòng "Đang chờ đủ 2 người trong phòng".
- Chuyển nút điều khiển chính vào khu vực giữa, ngay dưới ảnh VS.
- Chủ phòng chưa có đối thủ: hiển thị `Mời Đấu`.
- Máy khách trong phòng: hiển thị `Sẵn Sàng` và `Thoát Phòng`.
- Khi máy khách đã sẵn sàng: hiển thị `Hủy Sẵn Sàng` và `Thoát Phòng`.
- Sau khi hoàn thành trận: cả chủ phòng và máy khách đều hiển thị `Đá Tiếp` và `Thoát Phòng`.
- Bỏ các nút trùng lặp và các câu hướng dẫn dư ở khung điều khiển phía dưới.
- Giữ nguyên công thức RP và các chức năng khác của V1.11.1.

## File đã sửa

- `app.py`: cập nhật `APP_VERSION`.
- `templates/base.html`: rút gọn cách hiển thị phiên bản và bỏ trạng thái hệ thống.
- `templates/room_detail.html`: chuyển các nút điều khiển vào giữa phòng đấu.
- `static/style.css`: bổ sung bố cục nút điều khiển giữa phòng.

## Cài đặt

1. Sao lưu repository hiện tại hoặc tạo branch thử nghiệm.
2. Giải nén ZIP.
3. Chép toàn bộ file vào thư mục gốc repository.
4. Chọn ghi đè file trùng tên.
5. Commit và Push lên GitHub.
6. Deploy Vercel và kiểm tra bằng hai tài khoản người chơi.

Không cần chạy SQL và không cần thay đổi Supabase.
