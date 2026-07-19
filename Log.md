# Collap_V1.13.3l — Loại bỏ reload phòng và gom polling

- Bản nền: `Collap_V1.13.3k` cùng toàn bộ chuỗi nâng cấp từ `Collap_V1.13.2`.
- Ngày giờ: 19/07/2026 00:05 — múi giờ Asia/Bangkok.
- Loại gói: chỉ chứa các file cần chép đè.
- Không cần chạy SQL Supabase.

## 1. Trang phòng không còn tự tải lại toàn bộ

### Nguyên nhân cũ

`/api/room/<room-id>/state` chỉ trả `state_key`. Khi khóa thay đổi, JavaScript gọi:

```javascript
window.location.reload();
```

Mỗi lần trạng thái đổi, trình duyệt tải lại Document, CSS, JavaScript, ảnh Rank, VS, avatar và logo đội.

### Cách sửa

- Tách phần giao diện thay đổi thường xuyên sang `templates/_room_live_content.html`.
- API trạng thái chỉ render lại fragment này khi `state_key` thay đổi.
- Trình duyệt thay nội dung bên trong `#roomLiveContent`.
- Không gọi `location.reload()` hoặc `window.location.reload()` trong trang phòng.
- Không thay lại khung trang, sidebar, CSS hoặc các file JavaScript.
- Sau khi cập nhật fragment, tự đồng bộ lại:
  - đội và logo;
  - trạng thái sẵn sàng;
  - tỷ số và nút xác nhận;
  - nút đá tiếp/thoát phòng;
  - lịch sử tỷ số trong phòng;
  - đồng hồ;
  - chat phòng;
  - bản nháp tỷ số đang nhập.

## 2. Polling trạng thái phòng chỉ còn một luồng

- Chỉ có một timer trạng thái phòng trong `templates/room_detail.html`.
- Có khóa `roomStateRequestInFlight`, không cho request mới chạy khi request trước chưa xong.
- Nếu có yêu cầu kiểm tra ngay khi request đang chạy, chỉ đánh dấu chạy lại sau; không tạo request chồng.
- Không còn listener `focus` tạo lần gọi sát nhau.
- Khi tab được mở lại, gọi trạng thái ngay một lần rồi trở về chu kỳ bình thường.
- Khi tab ẩn, trạng thái phòng giãn thành khoảng 12 giây.

### Chu kỳ mới

| Trạng thái | Tab đang xem |
|---|---:|
| Chờ người/khách chưa vào | khoảng 5 giây |
| Chờ sẵn sàng, đã đủ người | khoảng 3 giây |
| Đang thi đấu — khách | khoảng 3 giây |
| Đang thi đấu — chủ phòng | khoảng 5 giây |
| Chờ xác nhận | khoảng 2 giây |
| Đã xác nhận/chờ đá tiếp | khoảng 3 giây |
| Tab ẩn | khoảng 12 giây |

## 3. Polling lời mời

- Players: khoảng 10 giây.
- BXH/sảnh/trang khác: khoảng 15 giây.
- Phòng chưa có khách: khoảng 12 giây.
- Phòng đã đủ hai người: dừng hoàn toàn.
- Đang thi đấu, chờ xác nhận hoặc đã xác nhận: dừng hoàn toàn.
- Tab ẩn: dừng.
- Mỗi trang chỉ có một poller `pending-invites`.

## 4. Session Activity

- Chỉ gửi sau khi người dùng thật sự click, gõ phím, chạm hoặc gửi form.
- Tối đa một request trong 60 giây.
- Lưu mốc đồng bộ trong `sessionStorage`, nên chuyển trang hoặc submit form không tạo lại request dày.
- Tab ẩn không gửi.
- Khi quay lại tab, kiểm tra và gửi tối đa một lần nếu đã đủ 60 giây.
- Có khóa chống request chồng.

## 5. Heartbeat, announcement, active-room và online-count

| Endpoint | Cách hoạt động mới |
|---|---|
| `/heartbeat` | khoảng 60 giây, dừng khi tab ẩn |
| `/api/announcement/current` | khoảng 60 giây, dừng khi tab ẩn |
| `/api/active-room` | bỏ polling định kỳ; dùng dữ liệu render khi tải trang và kiểm tra lại khi quay lại tab |
| `/api/online-count` | khoảng 60 giây trên Players, dừng khi tab ẩn |

Trang Lời mời không còn tạo thêm poller `/api/active-room` riêng mỗi 10 giây.

## 6. Cache file tĩnh

- `style.css`, `pes_polling.js` và `session-timeout.js` dùng `?v={{ APP_VERSION }}`.
- `app.py` đặt `Cache-Control: public, max-age=31536000, immutable` cho endpoint static.
- `vercel.json` đặt cùng cache header tại Vercel cho `/static/*`.
- Khi phiên bản không đổi, trình duyệt có thể dùng lại file cũ.
- Khi nâng phiên bản, URL mới buộc trình duyệt tải bản mới.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | khoảng dòng 65, 1472–1487, 3720–3810 | tăng phiên bản; cache static; mở rộng state key; API trả fragment động |
| `templates/room_detail.html` | toàn bộ vùng phòng và JS khoảng dòng 60–520 | dùng fragment; bỏ reload; một timer; cập nhật DOM; giữ draft tỷ số và modal |
| `templates/_room_live_content.html` | file mới | phần giao diện đội, tỷ số, nút, lịch sử và chat được render lại khi trạng thái đổi |
| `templates/base.html` | khoảng dòng 9–23, 223–350, 736–910 | version file tĩnh; gom invite polling; chỉnh heartbeat, announcement, active-room, online count |
| `templates/invites.html` | cuối file | bỏ active-room polling riêng 10 giây |
| `templates/chat.html` | cuối file | đặt khóa định danh cho poller chat |
| `static/js/pes_polling.js` | toàn file | registry theo key, tự dừng poller cũ cùng loại |
| `static/js/session-timeout.js` | khoảng dòng 7–140 | activity tối đa 1 lần/60 giây, lưu mốc qua chuyển trang, dừng khi tab ẩn |
| `vercel.json` | routes | cache dài cho `/static/*` |

## Kiểm tra đã thực hiện

- Python compile `app.py` và toàn bộ module: đạt.
- Parse 25 template Jinja: đạt.
- Kiểm tra cú pháp hai file JavaScript tĩnh bằng Node.js: đạt.
- Render thử trang phòng và kiểm tra toàn bộ JavaScript inline bằng Node.js: đạt.
- Số route trước/sau: giữ nguyên 100.
- `room_detail.html` không còn `location.reload()`.
- Trang phòng chỉ còn một vị trí gọi `/api/room/<id>/state`.
- Không có `__pycache__` hoặc `.pyc` trong gói.

## Cài đặt

Giải nén và chép đè các file vào dự án đang chạy `Collap_V1.13.3k`, sau đó deploy trên nhánh test. Không chép nguyên file ZIP vào repository.
