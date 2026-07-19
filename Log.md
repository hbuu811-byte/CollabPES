# Collap_V1.13.3lv1.3

- Ngày giờ: 19/07/2026, múi giờ Asia/Bangkok.
- Bản nền: Collap_V1.13.3lv1.2.
- Phạm vi: giảm modal thừa trong phòng đấu và đồng bộ các hộp xác nhận còn dùng giao diện trình duyệt.

## Nội dung sửa

1. Bỏ modal lớn sau các bước thành công thông thường:
   - Sẵn Sàng / Hủy Sẵn Sàng.
   - Quay đội hoặc quay lại đội giao hữu.
   - Nhập kết quả và chuyển sang chờ xác nhận.
   - Xác nhận kết quả / rút tranh chấp thành công.
   - Chọn Đá tiếp và chờ đối thủ.
   - Các bước trạng thái tương tự đã thể hiện trực tiếp trên giao diện phòng.

2. Giữ modal khi người chơi có ý định thoát phòng:
   - Thoát an toàn, không trừ RP.
   - Thoát khi đối thủ đã Sẵn Sàng hoặc trận đã bắt đầu, cảnh báo trừ 20 RP.
   - Kết thúc phiên đấu và trở về sảnh.

3. Giữ modal cho cảnh báo/lỗi quan trọng:
   - Lỗi dữ liệu, kết nối, quyền thao tác và trạng thái không hợp lệ.
   - Phiên đăng nhập hết hạn.
   - Đối thủ rời phòng hoặc yêu cầu đá tiếp hết hạn.

4. Đồng bộ hai hộp xác nhận còn dùng `confirm()` của trình duyệt:
   - Gửi tranh chấp.
   - Rút tranh chấp và chấp nhận kết quả.
   Hai thao tác này giờ dùng chung modal PES Arena.

## File đã sửa

- `app.py` khoảng dòng 65: tăng APP_VERSION thành Collap_V1.13.3lv1.3.
- `templates/room_detail.html` khoảng dòng 103–125, 170–255, 460–475, 666–835 và 1230–1395:
  lọc thông báo trạng thái thường, chuẩn hóa nội dung thoát phòng và đồng bộ hộp xác nhận tranh chấp.

## Không thay đổi

- Không sửa RP hoặc mức phạt 20 RP.
- Không sửa polling, chat, lời mời, cache hoặc API trạng thái phòng.
- Không sửa lịch sử đấu và lịch sử bỏ cuộc.
- Không sửa Supabase và không cần chạy SQL.
