# Log — Collap_V1.13.3k

- **Phiên bản nền:** Collap_V1.13.3j
- **Phiên bản mới:** Collap_V1.13.3k
- **Ngày giờ:** 18/07/2026 23:47
- **Múi giờ:** Asia/Bangkok
- **Phạm vi:** Sửa lỗi HTTP 500 khi người chơi xác nhận **Bỏ cuộc và thoát**.

## Nguyên nhân trong code

Tính năng ghi trận bỏ cuộc ở bản trước có hai nhánh ghi Supabase:

1. Payload đầu tiên có các cột nâng cấp tùy chọn như `loser_id` và `rp_details`. Cấu trúc Supabase chưa chạy SQL nâng cấp có thể không có các cột này.
2. Nhánh ghi dự phòng đã bỏ các cột tùy chọn, nhưng khi tạo trận bỏ cuộc trước lúc quay đội lại không gửi đủ nhóm trường mà luồng tạo trận bình thường đang sử dụng như đội, overall và `host_xp_factor`.
3. Nếu nhánh dự phòng tiếp tục lỗi, exception bị đẩy ra route Flask và tạo trang **Internal Server Error**.

## Nội dung đã sửa

### `app.py`

- Khoảng dòng **64–66**:
  - Đổi phiên bản hiển thị thành `Collap_V1.13.3k`.

### `modules/forfeit_history_service.py`

- Khoảng dòng **91–127**:
  - Tách payload dành cho trận đã có `match_id`.
  - Chỉ cập nhật các cột đã được dự án sử dụng ổn định.

- Khoảng dòng **130–165**:
  - Tạo payload riêng cho trường hợp bỏ cuộc trước lúc quay đội.
  - Bổ sung `team1`, `team2`, `team1_overall`, `team2_overall` và `host_xp_factor` giống luồng tạo trận bình thường.
  - Khi chưa quay đội, dùng nhãn `Chưa quay đội`; lịch sử giao diện vẫn hiển thị **Bỏ cuộc**, không tạo tỷ số giả.
  - Không còn phụ thuộc vào `loser_id` hoặc `rp_details`, vì hai cột này có thể chưa tồn tại nếu chưa chạy SQL nâng cấp.

- Khoảng dòng **168–175**:
  - Thêm hàm ghi cảnh báo an toàn vào log.

- Khoảng dòng **178–240**:
  - Cô lập toàn bộ lỗi ghi lịch sử Supabase.
  - Lỗi phụ khi gắn `match_id` vào phòng không còn làm hỏng thao tác chính.
  - Nếu Supabase tạm lỗi, route bỏ cuộc không còn trả HTTP 500.
  - Giữ marker `[FORFEIT:host]` / `[FORFEIT:guest]` trong `note` để xác định chính xác người thua mà không cần sửa SQL.

## Logic không thay đổi

- Người bỏ cuộc vẫn bị trừ đúng mức RP hiện hành.
- Vẫn cộng một trận thua cho người bỏ cuộc.
- Đối thủ không được cộng RP và không được cộng trận thắng.
- Trận bỏ cuộc vẫn được ghi vào lịch sử khi Supabase nhận lệnh thành công.
- Không sửa công thức RP.
- Không cần chạy SQL Supabase.
- Không thay đổi giao diện phòng hoặc bảng lịch sử tỷ số.

## Kiểm tra đã thực hiện

- `python -m py_compile app.py modules/*.py`: **Đạt**.
- `python test_rp_engine.py`: **Đạt — RP_V1.12.0**.
- Parse 24 template Jinja: **Đạt**.
- Test tạo lịch sử bỏ cuộc trước lúc quay đội với schema yêu cầu đủ trường: **Đạt**.
- Test cập nhật trận bỏ cuộc đã có `match_id`: **Đạt**.
- Test ép Supabase lỗi: hàm trả về an toàn, không ném exception ra route: **Đạt**.
- Không thể chạy full import Flask trong môi trường đóng gói hiện tại vì môi trường không cài thư viện `flask`; không phát hiện lỗi cú pháp Python hoặc Jinja.

## File cần chép đè

```text
app.py
modules/forfeit_history_service.py
```

`Log.md` chỉ dùng để lưu lịch sử thay đổi.
