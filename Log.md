# PES 2026 WEB V1.10.12 – Modular Core

## Mục tiêu

Giữ nguyên route, giao diện và luồng nghiệp vụ của bản V1.10.11, nhưng tách các phần lõi ra khỏi `app.py` để có thể nâng cấp và kiểm thử từng phần độc lập.

## Các module mới

| Module | Chức năng | Khi cần nâng cấp |
|---|---|---|
| `modules/rp_engine.py` | Công thức cộng/trừ RP, placement và thưởng chuỗi | Sửa công thức RP tại đây; route phòng đấu không cần đổi |
| `modules/win_streaks.py` | HAT-TRICK, POKER, SHUTDOWN và dữ liệu animation | Sửa mốc, tên danh hiệu hoặc nội dung thông báo tại đây |
| `modules/cache_utils.py` | Cache theo request và TTL RAM ngắn | Tối ưu polling/cache mà không chạm route |
| `modules/datetime_utils.py` | UTC, thời gian hết hạn và định dạng giờ Việt Nam | Sửa quy tắc thời gian tập trung tại đây |
| `modules/__init__.py` | Khai báo package module | Giữ cấu trúc import ổn định |

## Tương thích

- Giữ nguyên toàn bộ URL/route Flask hiện có.
- Giữ nguyên tên hàm `calculate_deltas(...)` trong `app.py` bằng lớp tương thích.
- Giữ nguyên dữ liệu Supabase, template, CSS và static.
- Không thay đổi cấu trúc bảng dữ liệu.
- Không thay đổi công thức RP đang chạy trong bản nguồn.
- Không thay đổi cách hiển thị danh hiệu/animation hiện có.

## Kiểm tra đã thực hiện

- `python -m py_compile app.py modules/*.py`: đạt.
- Kiểm thử mẫu cho thắng/thua/hòa của RP engine: đạt.
- Kiểm thử tạo, mã hóa và đọc sự kiện HAT-TRICK: đạt.
- Chưa thể chạy import toàn bộ Flask trong môi trường đóng gói vì môi trường hiện tại không cài dependency `flask`; Vercel sẽ cài theo `requirements.txt` như bản cũ.

## Hướng nâng cấp tiếp theo

Các nhóm route lớn vẫn nằm trong `app.py` để tránh thay đổi rủi ro trong một lần. Có thể tách tuần tự ở các phiên bản sau theo thứ tự:

1. `routes/auth.py`
2. `routes/rooms.py`
3. `routes/profiles.py`
4. `routes/admin.py`
5. `services/supabase_repository.py`

Mỗi bước nên tách một nhóm, deploy nhánh test, kiểm tra rồi mới merge vào `main`.

---

## Lịch sử bản nguồn

## v1.10.11 - Danh hiệu chuỗi, sửa RP thua, logo giải đấu

- Thêm huy hiệu chuỗi thắng từ HAT-TRICK! đến BEYOND GODLIKE! tại phòng đấu, hồ sơ, Players và BXH.
- Thêm khung thông báo lớn giữa màn hình và toast SHUTDOWN/danh hiệu theo phong cách esports vàng.
- Sửa bảo vệ công thức để trận phân thắng bại luôn trừ RP người thua và cộng RP người thắng.
- Hiển thị logo giải đấu từ Supabase Storage: `team-logos/league-logos`.

# Log

## WIN_STREAK_FEATURE_GOLD_V2

- Thêm danh hiệu chuỗi thắng Rank từ 3 đến 10+ trận.
- Thêm SHUTDOWN khi đánh bại người có chuỗi từ 3 trận trở lên.
- Giao hữu không tính và không phá chuỗi.
- Thêm huy hiệu cố định, thông báo lớn khung vàng 4 giây và toast 6/8 giây.
- Không cần SQL mới.
- Được ghép bằng file `apply_win_streak_feature_gold_frame_v2.py`.

## V1.10.10

- Khi chủ phòng gửi kết quả, hình `VS` được thay trực tiếp bằng tỷ số ở giữa phòng đấu.
- Tỷ số của hai bên đều dùng màu trắng.
- Sân khách thấy hai nút `Xác Nhận` và `Không Đồng Ý` ngay dưới tỷ số.
- Nút `Không Đồng Ý` mở biểu mẫu tranh chấp tại khu vực giữa.
- Sân nhà cũng thấy cùng tỷ số và trạng thái đang chờ sân khách xác nhận.
- Loại bỏ cụm xác nhận kết quả bị lặp ở phần nội dung phía dưới.
- Cập nhật phiên bản thành `V1.10.10`.

## V1.10.9

- Bỏ hình xúc xắc khỏi khu vực quay random đội ở phòng đấu.
- Giữ nguyên nút `QUAY RANDOM ĐỘI`, trạng thái chờ và toàn bộ cơ chế random đội.
- Cập nhật phiên bản thành `V1.10.9`.

## V1.10.8

- Thay file `static/xucxac.png` bằng đúng ảnh xúc xắc mới người dùng cung cấp.
- Thêm tham số phiên bản vào URL ảnh để trình duyệt không dùng ảnh lỗi đã cache.
- Giữ xúc xắc đầy đủ màu sắc ở cả giao diện chủ phòng và đội khách.
- Đội khách hiển thị chữ `ĐỢI QUAY RANDOM ĐỘI`.
- Chủ phòng chưa thể quay vì khách chưa sẵn sàng sẽ thấy `ĐỢI KHÁCH SẴN SÀNG`.
- Chủ phòng đủ điều kiện vẫn thấy `QUAY RANDOM ĐỘI` và có thể bấm để quay.
- Cập nhật phiên bản thành `V1.10.8`.
