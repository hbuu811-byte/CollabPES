# Log — Collap_V1.13.3lv2.2

- Ngày giờ: 19/07/2026 01:43, múi giờ Asia/Bangkok.
- Nhánh nền: `Collap_V1.13.3lv2.1`.
- Loại gói: bản vá, chỉ gồm các file cần chép đè.
- SQL Supabase: không cần.
- Không sửa RP, lịch sử trận, phạt bỏ cuộc, modal phòng, công thức Rank hoặc dữ liệu Supabase.

## Mục tiêu

Hoàn thiện các phần request/polling còn có nguy cơ treo hoặc tiếp tục chạy sau khi người dùng rời trang, đồng thời giảm giật phần chat khi trạng thái phòng thay đổi.

## Nội dung đã sửa

### 1. Request không còn giữ khóa vô thời hạn

- `/api/room/<room-id>/state`: thời gian chờ tối đa 12 giây.
- `/api/room/<room-id>/chat`: thời gian chờ tối đa 10 giây.
- Gửi chat phòng: thời gian chờ tối đa 12 giây.
- `/api/invites/pending`: thời gian chờ tối đa 10 giây.
- Khi request quá thời gian, request bị hủy và khóa được giải phóng để chu kỳ sau thử lại.
- Không tạo request mới khi request cùng khóa vẫn đang chạy.

### 2. Dừng toàn bộ request cũ khi rời trang

- `pes_polling.js` bổ sung lớp dọn chung cho `pagehide` và `beforeunload`.
- Khi trang thực sự rời đi: dừng toàn bộ poller và hủy toàn bộ request còn chạy.
- Khi trang được giữ trong BFCache: chỉ hủy request đang chạy, giữ poller ở trạng thái có thể tiếp tục khi quay lại.
- Không thay đổi logic riêng của phòng đấu đã có trong bản `lv2.1`.

### 3. Xử lý phiên đăng nhập hết hạn

- State, chat và lời mời nhận biết trường hợp API bị chuyển hướng sang trang đăng nhập.
- Không cố phân tích HTML đăng nhập thành JSON.
- State dừng realtime và đưa người dùng về trang đăng nhập.
- Chat/lời mời dừng poller thay vì tiếp tục gọi ngầm.
- HTML lỗi 5xx không bị hiểu nhầm thành hết phiên; poller giữ giao diện và thử lại ở chu kỳ sau.

### 4. Giữ nguyên khung chat khi phòng cập nhật trạng thái

- Khi đội, tỷ số, nút hoặc lịch sử thay đổi, vùng phòng vẫn cập nhật bằng fragment như bản trước.
- Riêng DOM của chat phòng được giữ nguyên.
- Không làm mất nội dung người dùng đang gõ.
- Không làm mất vị trí cuộn chat.
- Không tạo thêm request chat chỉ vì đội hoặc nút trong phòng thay đổi.
- Chỉ khởi động/dừng chat nếu khung chat thực sự xuất hiện hoặc bị loại khỏi giao diện.

### 5. Cache CSS trên các trang độc lập

- `public_ranking.html` dùng `style.css?v={{ APP_VERSION }}`.
- `maintenance.html` bỏ số phiên bản cũ cố định và dùng `APP_VERSION` hiện tại.
- Giữ nguyên cache một năm `immutable` đã có ở Flask/Vercel.

## File đã chỉnh sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | khoảng dòng 65 | tăng phiên bản thành `Collap_V1.13.3lv2.2` |
| `static/js/pes_polling.js` | khoảng dòng 220–305 | metadata response, timeout cleanup, nhận biết HTML redirect, dọn poller/request khi rời trang |
| `templates/room_detail.html` | khoảng dòng 318–465, 618–760 | giữ DOM chat; timeout và xử lý hết phiên cho state/chat/gửi chat |
| `templates/base.html` | khoảng dòng 337–395 | timeout, khóa và xử lý hết phiên cho lời mời |
| `templates/public_ranking.html` | khoảng dòng 10 | thêm phiên bản URL CSS |
| `templates/maintenance.html` | khoảng dòng 7 | thay version CSS cố định bằng `APP_VERSION` |

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse 25 template Jinja: đạt.
- Render thử `room_detail.html`, `public_ranking.html`, `maintenance.html`: đạt.
- Kiểm tra cú pháp toàn bộ JavaScript nội tuyến của trang phòng: đạt.
- `node --check static/js/pes_polling.js`: đạt.
- Ba request cùng khóa chỉ chạy task một lần: đạt.
- Response HTML 200 được nhận biết là redirect đăng nhập: đạt.
- Response HTML 500 không bị nhận nhầm là redirect đăng nhập: đạt.
- Điểm gọi state trong giao diện: 1.
- Điểm gọi lời mời trong giao diện: 1 hàm, có nhánh fallback khi thiếu `PESNet`.
- Điểm gọi chat phòng: 1 hàm, có nhánh fallback khi thiếu `PESNet`.
- `location.reload()` trong `room_detail.html`: 0.
- Link static trong template thiếu `?v=`: 0.

## Cài đặt

Chép đè các file trong gói này lên nhánh `Collap_V1.13.3lv2.1`. Không áp dụng sang hai nhánh song song khác nếu chưa đối chiếu riêng.
