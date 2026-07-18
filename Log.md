# Collap_V1.13.3f — Đồng bộ thông báo kết thúc phiên đấu

- **Phiên bản nền:** `Collap_V1.13.3e`
- **Ngày giờ:** 18/07/2026 19:00 — múi giờ Asia/Bangkok
- **Loại phát hành:** Gói vá, chỉ chứa các file cần thay
- **SQL Supabase:** Không cần

## Nội dung sửa

### 1. Người chủ động thoát sau khi trận đã hoàn thành

Sau khi trận ở trạng thái `confirmed`, nút **Thoát Phòng** không còn gửi form ngay lập tức.
Hệ thống mở modal giữa màn hình theo giao diện PES Arena để xác nhận:

- Không muốn đá tiếp.
- Đối thủ sẽ nhận được thông báo.
- Cả hai được đưa về sảnh chính.
- Không trừ RP vì trận trước đã hoàn thành.

### 2. Người còn lại trong phòng

Khi đối thủ chọn thoát sau trận, polling trạng thái phòng mở modal game với đúng nội dung:

> Đối thủ không muốn đá tiếp. Bạn sẽ được đưa về sảnh chính.

Modal:

- Không dùng `window.alert()` của trình duyệt.
- Hiển thị giữa màn hình, đồng bộ với modal thoát phòng hiện có.
- Có nút **Về sảnh chính**.
- Tự chuyển về sảnh sau 5 giây nếu người dùng không bấm nút.
- Không thể tắt bằng nút ×, vùng nền hoặc phím Esc để tránh bỏ lỡ trạng thái kết thúc phòng.

### 3. Hết hạn yêu cầu đá tiếp

Thông báo hết hạn 60 giây cũng được chuyển từ `window.alert()` sang modal game và tự về sảnh sau 4,5 giây.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | dòng 65 | Tăng phiên bản lên `Collap_V1.13.3f` |
| `templates/room_detail.html` | dòng 223–237 | Thêm modal xác nhận cho nút Thoát Phòng sau trận confirmed |
| `templates/room_detail.html` | dòng 711–753 | Thay alert đối thủ rời phòng/hết hạn bằng modal game |
| `templates/room_detail.html` | dòng 902–1050 | Mở rộng modal dùng chung để hỗ trợ chế độ thông báo và tự chuyển trang |

## Logic giữ nguyên

- Không thay đổi công thức RP.
- Không thay đổi kết quả trận đã xác nhận.
- Không thay đổi lịch sử phòng đấu.
- Không thay đổi phạt bỏ cuộc 20 RP trước hoặc trong khi thi đấu.
- Không thay đổi Supabase hoặc cấu trúc bảng.
- Không thêm polling mới.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse toàn bộ 24 template Jinja: đạt.
- Kiểm tra cú pháp JavaScript của module modal: đạt.
- Không còn chuỗi `window.alert("Đối thủ không muốn đá tiếp...")`.
- Thông báo đối thủ rời phòng giữ đúng nguyên văn yêu cầu.
- Diff với `Collap_V1.13.3e`: chỉ thay `app.py` và `templates/room_detail.html`.

## Cài đặt

1. Dùng dự án đã áp dụng đến `Collap_V1.13.3e`.
2. Giải nén ZIP.
3. Chép đè `app.py` và `templates/room_detail.html` vào repository.
4. Commit, Push và deploy lên nhánh test.
5. Test bằng hai trình duyệt: hoàn thành trận, một bên bấm **Thoát Phòng**, kiểm tra bên còn lại nhìn thấy modal trước khi về sảnh.
