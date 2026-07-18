# Collap_V1.13.3i — Ghi lịch sử trận thua do bỏ cuộc

- Ngày giờ: 18/07/2026 22:37 — Asia/Bangkok
- Phiên bản nền: `Collap_V1.13.3h`
- Phạm vi: chỉ sửa luồng bỏ cuộc và phần hiển thị lịch sử liên quan.
- SQL Supabase: không cần.

## Nội dung đã sửa

1. Mọi lần người chơi bị tính thua do bỏ cuộc đều có bản ghi trong bảng `matches`.
   - Nếu trận đã được tạo sau khi quay đội: cập nhật chính trận đó thành bản ghi bỏ cuộc.
   - Nếu bỏ cuộc ngay sau khi Sẵn Sàng, trước khi quay đội: tạo một bản ghi lịch sử mới.
   - Áp dụng cho khách bỏ cuộc, chủ phòng bỏ cuộc và bỏ trận do hết thời gian.

2. Không thay đổi quy tắc điểm hiện tại.
   - Người bỏ cuộc vẫn bị trừ đúng mức phạt đang chạy: `-20 RP` hoặc mức timeout hiện hành.
   - Người còn lại không được cộng RP và không được cộng một trận thắng.
   - Chỉ người bỏ cuộc được cộng thêm một trận thua như logic cũ.

3. Hiển thị rõ trong lịch sử.
   - Người bỏ cuộc thấy `THUA BỎ CUỘC` và số RP bị trừ.
   - Người còn lại thấy `ĐỐI THỦ BỎ CUỘC` và `+0 RP`.
   - Tỷ số hiển thị `Bỏ cuộc`, không giả lập tỷ số thắng/thua.
   - Ghi chú kỹ thuật `[FORFEIT:host/guest]` được ẩn khỏi giao diện.

4. Tương thích dữ liệu cũ.
   - Nhận diện các dòng `cancelled` cũ có ghi chú bỏ cuộc hoặc chỉ có một delta âm.
   - Nếu Supabase thiếu cột tùy chọn `loser_id` hoặc `rp_details`, hệ thống tự thử lại bằng payload tối thiểu thay vì làm mất bản ghi lịch sử.

5. Làm mới cache sau khi phạt và ghi lịch sử để RP/lịch sử hiện ngay, không phải chờ cache hết hạn.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | dòng 65 | Nâng phiên bản lên `Collap_V1.13.3i` |
| `app.py` | dòng 1984–2105 | Nhận diện và trình bày trận bỏ cuộc theo đúng người thua |
| `app.py` | dòng 2433–2490 | Làm mới cache và ghi lịch sử cho phạt timeout |
| `app.py` | dòng 4670–4685 | Đưa trận thua bỏ cuộc vào phong độ gần đây của người bị phạt |
| `app.py` | dòng 5039–5055 | Đăng ký service lịch sử bỏ cuộc |
| `modules/forfeit_history_service.py` | toàn file | Module mới tạo/cập nhật bản ghi bỏ cuộc an toàn |
| `modules/room_rematch_routes.py` | dòng 53–68, 129–142 | Ghi lịch sử cho khách/chủ phòng bỏ cuộc |
| `templates/matches.html` | dòng 15–55 | Hiển thị trận bỏ cuộc trong trang Lịch sử trận |
| `templates/profile.html` | dòng 214–232 | Hiển thị trận bỏ cuộc trong Hồ sơ người chơi |
| `templates/dashboard.html` | dòng 63–68 | Hiển thị RP bỏ cuộc trong Hoạt động gần đây |

## Kiểm tra đã thực hiện

- `python -m py_compile` cho `app.py` và các module sửa: đạt.
- Parse đủ 24 template Jinja: đạt.
- Số route trước/sau: giữ nguyên `100/100`.
- Mô phỏng khách bỏ cuộc trước khi quay đội: tạo bản ghi mới, `delta2=-20`, người thua là khách.
- Mô phỏng chủ phòng bỏ cuộc khi đã có trận: cập nhật đúng trận, `delta1<0`, người thua là chủ.
- Kiểm tra góc nhìn lịch sử: người bỏ cuộc thấy `THUA BỎ CUỘC`; đối thủ thấy `ĐỐI THỦ BỎ CUỘC`.

## Lưu ý

- Bản vá ghi đầy đủ cho các lần bỏ cuộc phát sinh sau khi triển khai.
- Các lần bỏ cuộc cũ trước đây không tạo bất kỳ dòng nào trong `matches` thì không thể tự khôi phục chính xác chỉ từ code, vì không còn đủ dữ liệu thời điểm và cặp đấu.
