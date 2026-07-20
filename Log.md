# Collap_V1.13.3lv3.5 — Sửa khung Rank/CLB phóng toàn màn hình

- Ngày giờ: 20/07/2026 09:47, múi giờ Asia/Bangkok.
- Bản nền bắt buộc: `Collap_V1.13.3lv3.4`.
- Loại gói: trình vá an toàn.
- SQL Supabase: không cần.

## Lỗi quan sát được

Trong phòng chưa quay đội, thẻ Chủ phòng chứa khung Rank và vùng CLB bị kéo ngang gần toàn bộ màn hình; biểu tượng VS rơi xuống phía dưới thay vì nằm giữa hai người chơi.

## Nguyên nhân

`lv3.4` dùng bộ morph DOM đệ quy, ghép node theo vị trí trong `childNodes`. HTML phòng có nhiều text node, comment, form và phần tử xuất hiện/biến mất theo trạng thái. Khi một node được di chuyển, chỉ số các node sau thay đổi nhưng thuật toán vẫn tiếp tục dựa trên chỉ số cũ. Kết quả là các thẻ `.home`, `.center`, `.away` có thể bị đưa ra khỏi `.room-match-shell` hoặc bị xóa nhầm, làm grid ba cột bị vỡ.

Đây không phải lỗi kích thước ảnh Rank và không cần sửa ảnh hoặc dữ liệu CLB.

## Cách sửa

### `templates/room_detail.html`

- Xóa hoàn toàn `roomNodeKey()`, `syncRoomAttributes()` và `morphRoomNode()` của `lv3.4`.
- Không ghép lại từng text node hoặc từng node con.
- Chỉ so sánh và thay các vùng ổn định:
  1. thông báo chuỗi thắng;
  2. thanh thông tin phòng;
  3. thẻ Chủ phòng;
  4. vùng giữa/VS/tỷ số;
  5. thẻ Khách;
  6. thông tin bên phải;
  7. lịch sử và điều khiển phòng;
  8. trạng thái xuất hiện hoặc biến mất của chat.
- Giữ nguyên DOM chat nếu chat vẫn đang bật, tránh mất tin nhắn, nội dung đang gõ và vị trí cuộn.
- Kiểm tra cấu trúc bắt buộc của `.room-match-shell` trước khi áp dụng HTML mới.
- Nếu DOM đã bị `lv3.4` làm hỏng, tự phục hồi riêng `#roomLiveContent`; không reload toàn bộ trang.
- Đổi cache key sang `pes-room-fragment-cache-v2:<room_id>` và xóa cache cũ của `lv3.4`.
- Tiếp tục giữ tỷ số đang nhập, focus và vị trí con trỏ bằng cơ chế snapshot hiện có.

### `app.py`

- Tăng `APP_VERSION` lên `Collap_V1.13.3lv3.5` để trình duyệt nhận đúng phiên bản mới.

## File được sửa sau khi chạy

| File | Vị trí ước lượng | Nội dung |
|---|---:|---|
| `app.py` | khoảng dòng 65 | tăng phiên bản |
| `templates/room_detail.html` | khu vực `roomNodeKey()` đến `patchRoomLiveContent()` | thay thuật toán morph bằng fragment cố định và tự sửa grid |

## Không thay đổi

- Không sửa CSS hoặc kích thước ảnh Rank.
- Không sửa RP, lịch sử đấu, bỏ cuộc, Admin hoặc Supabase.
- Không thay đổi polling, chat API hoặc khoảng watchdog của `lv3.4`.
- Không đưa lại `location.reload()`.
- Không tải lại `base.html`, CSS, JavaScript hoặc toàn bộ Document khi sự kiện phòng thay đổi.

## Cài đặt

1. Chép ba file trong ZIP vào thư mục gốc dự án `Collap_V1.13.3lv3.4`.
2. Nhấp đúp `APPLY_Collap_V1.13.3lv3.5.bat`.
3. Commit đúng:
   - `app.py`;
   - `templates/room_detail.html`.
4. Không commit thư mục `.collap_v1_13_3lv3_5_backup`.
5. Push và redeploy Vercel.

## Kịch bản test

1. Chủ phòng tạo phòng khi chưa có khách: thẻ Chủ, VS và thẻ Khách phải nằm cùng hàng.
2. Khách vào phòng: chỉ thẻ Khách và nút liên quan đổi, bố cục không giãn toàn màn hình.
3. Khách bấm Sẵn sàng: vùng giữa đổi nút, không reload trang.
4. Quay đội: logo/tên đội hai bên đổi nhưng grid giữ nguyên.
5. Đang nhập tỷ số và có cập nhật khác: ô tỷ số không bị reset.
6. Gửi chat rồi đổi trạng thái phòng: tin nhắn và nội dung đang gõ không mất.
