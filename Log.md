# Log — PES Arena V1.13.13-v4.9.2

- **Ngày giờ:** 18/07/2026 12:57 — múi giờ Asia/Bangkok
- **Gói sửa:** `PES_Arena_V1.13.13-v4.9.2_Sua_Hien_Thi_Ben_Thang_Ben_Thua.zip`
- **Phiên bản đối chiếu:** `PES_Arena_V1.13.13-v4.9.1_Admin_Doi_Trang_Thai_Tinh_Lai_Lich_Su.zip`
- **File vá người dùng gửi để tham khảo:** `fix_profile_match_result_v1_13_13(1).py`
- **Phạm vi:** Chỉ sửa phần hiển thị kết quả tại Lịch sử, Hồ sơ và dữ liệu trang Dashboard dùng chung hàm trang trí trận. Không sửa database, không thay đổi thời gian trận và không thay đổi công thức RP.

## Nguyên nhân lỗi

1. Hồ sơ luôn đặt người đang xem ở bên trái nhưng `score_display` vẫn dùng thứ tự gốc `score1 - score2`.
2. Lịch sử “Trận của tôi” tính nhãn THẮNG/THUA theo người đăng nhập, nhưng tên, CLB và tỷ số vẫn hiển thị theo thứ tự `player1 - player2`.
3. Khi người đang xem là `player2`, nhãn THẮNG có thể nằm cạnh phía hiển thị đối thủ, tạo cảm giác hệ thống xác định sai bên thắng và bên thua.
4. So sánh tỷ số trực tiếp chưa chuẩn hóa kiểu dữ liệu; nếu Supabase trả chuỗi số như `"10"` và `"2"`, việc so sánh có nguy cơ sai.
5. Trường `winner_id`/`loser_id` cũ có thể chưa đồng bộ ở một số dữ liệu lịch sử. Giao diện cần lấy tỷ số đã xác nhận làm nguồn sự thật khi hiển thị.

## Nội dung đã sửa

### 1. `app.py`

- **Khoảng dòng 1951–2120:**
  - Thêm chuẩn hóa tỷ số về số nguyên nhưng vẫn giữ `None` khi chưa nhập.
  - Chuẩn hóa delta RP từ int, float hoặc chuỗi số.
  - So sánh ID an toàn khi dữ liệu Supabase trả kiểu khác nhau.
  - Tạo một thứ tự hiển thị thống nhất `left/right`.
  - Trong Hồ sơ và “Trận của tôi”, người đang được xem luôn nằm bên trái.
  - Tỷ số, CLB, avatar, danh hiệu, delta RP và nhãn THẮNG/THUA được đảo đồng bộ cùng người chơi.
  - Bên thắng/bên thua hiển thị được tính lại từ `score1/score2` của trận confirmed, không tin mù quáng vào `winner_id/loser_id` cũ.
  - Hòa, hủy, tranh chấp và chờ xác nhận có nhãn riêng đúng trạng thái.

- **Khoảng dòng 5963–5967:**
  - Chế độ “Trận của tôi” truyền người đăng nhập làm góc nhìn.
  - Chế độ “Toàn hệ thống” giữ thứ tự gốc `player1/player2`, tránh việc mỗi thẻ bị đảo theo người đang đăng nhập.

### 2. `templates/matches.html`

- **Khoảng dòng 33–49:**
  - Dùng các trường `left_player_*` và `right_player_*` thay cho việc gắn cứng `player1/player2`.
  - Tên, avatar, CLB, tỷ số và RP luôn cùng một phía.
  - Hiển thị rõ nhãn THẮNG, THUA hoặc HÒA dưới từng người chơi đối với trận confirmed.
  - Chế độ toàn hệ thống hiển thị delta RP theo đúng phía trái/phải.

### 3. `templates/profile.html`

- **Khoảng dòng 214–229:**
  - Người sở hữu hồ sơ luôn nằm bên trái.
  - Đối thủ luôn nằm bên phải.
  - Tỷ số được hiển thị theo góc nhìn của người sở hữu hồ sơ.
  - Avatar, CLB, tên người chơi, nhãn THẮNG/THUA và RP không còn bị lệch phía.

## Ví dụ sau khi sửa

Trận gốc trong database:

- `player1 = An`, `score1 = 1`
- `player2 = Bình`, `score2 = 3`

Khi mở Hồ sơ của Bình:

- Bên trái: Bình — 3 — THẮNG
- Bên phải: An — 1 — THUA
- Tỷ số: `3 - 1`

Khi mở Toàn hệ thống:

- Bên trái giữ An — 1 — THUA
- Bên phải giữ Bình — 3 — THẮNG
- Tỷ số: `1 - 3`

## Kiểm tra đã thực hiện

- `python -m py_compile app.py`: đạt.
- Kiểm tra cú pháp Jinja `matches.html`, `profile.html`, `admin.html`: đạt.
- Người xem là player1 và thắng: đạt.
- Người xem là player1 và thua: đạt.
- Người xem là player2 và thắng: đạt.
- Người xem là player2 và thua: đạt.
- Tỷ số chuỗi `"2" - "10"`: xác định đúng người thắng, không so sánh theo chữ.
- Trận hòa: đạt.
- Trận hủy: hiển thị “Không tính”, đạt.
- `winner_id` cũ bị sai nhưng tỷ số đúng: giao diện vẫn hiển thị đúng bên thắng/bên thua.

## File cần thay

```text
app.py
templates/matches.html
templates/profile.html
```

Không cần chạy SQL và không cần thay file khác.
