# Log — Collap_V1.13.3lv2.1

- Ngày giờ: 19/07/2026 01:29, múi giờ Asia/Bangkok.
- Nhánh nền: `Collap_V1.13.3lv2` — cùng nội dung kỹ thuật với `Collap_V1.13.3l`.
- Loại gói: bản vá, chỉ gồm các file cần chép đè.
- SQL Supabase: không cần.

## Mục tiêu kiểm tra

1. Sửa API chat phát sinh 403 trong luồng sử dụng bình thường.
2. Chỉ giữ một bộ polling trạng thái phòng.
3. Dừng polling/request cũ khi chuyển trang hoặc rời phòng.
4. Không reload toàn bộ trang phòng khi trạng thái thay đổi.
5. Ngăn `/api/invites/pending` chạy đồng thời từ nhiều script.
6. Thêm khóa request đang chạy cho trạng thái phòng, chat và lời mời.
7. Tăng cache cho CSS, JavaScript, ảnh Rank và ảnh giao diện.

## Lỗi phát hiện và nội dung đã sửa

### 1. Fragment trạng thái phòng có thể trả lỗi 500

- `templates/_room_live_content.html` thiếu import macro `player_avatar` khi được API `/state` render trực tiếp.
- Đã import macro ngay trong fragment.
- `app.py` giữ lớp bảo vệ: lỗi render tạm thời trả JSON 503 thay vì làm sập trang phòng.

### 2. Chat có thể chạy chồng và phát sinh 403 giả sau khi rời phòng

- Chỉ giữ một poller chat có khóa `room-chat:<room_id>`.
- Thêm khóa riêng cho gửi tin nhắn.
- Gửi chat bằng AJAX, không reload cả trang.
- Khi người chơi vừa rời phòng hoặc Admin vừa tắt chat, API GET trả lệnh `stop_polling` bình thường, không trả 403 giả.
- Truy cập gửi tin nhắn trái phép thật sự vẫn bị chặn ở backend.
- Dừng và hủy request chat trước khi rời phòng/chuyển trang.

### 3. Polling trạng thái phòng

- Chỉ còn một điểm gọi `api_room_state` trong toàn bộ template/script.
- Dùng một timer `roomStateTimer`, một cờ in-flight và một `AbortController`.
- Không dùng `location.reload()` hoặc `window.location.reload()` trong phòng.
- API chỉ trả fragment HTML động; client chỉ thay `#roomLiveContent`.
- Không tạm dừng polling chỉ vì người dùng đang gõ chat; chỉ bảo vệ form tỷ số chưa gửi.

### 4. Polling lời mời

- Toàn bộ giao diện chỉ còn một điểm gọi `/api/invites/pending`.
- Poller được đăng ký bằng khóa `pending-invites`; tạo lại sẽ dừng poller cũ.
- Request được khóa bằng `pending-invites-request`.
- Phòng đủ hai người, đang thi đấu hoặc chờ xác nhận sẽ dừng kiểm tra lời mời.
- Tab ẩn không kiểm tra lời mời.

### 5. Dừng polling cũ

- Dừng timer/request phòng khi gửi form chuyển trang.
- Dừng ngay khi xác nhận bỏ cuộc hoặc rời phòng.
- Dừng ngay khi bấm liên kết nội bộ, không đợi tới lúc trang cũ bị hủy.
- Xử lý `pagehide`, `beforeunload` và BFCache `pageshow`.
- `pes_polling.js` gỡ toàn bộ event listener khi poller dừng, tránh tích lũy listener sau nhiều lần cấu hình lại.

### 6. Cache file tĩnh

- Giữ cấu hình cache một năm, `immutable`, cho toàn bộ `/static/` trong `vercel.json` và Flask của nhánh nền.
- CSS và JavaScript đã có `?v={{ APP_VERSION }}`.
- Bổ sung version cho ảnh Rank, ảnh VS, ảnh podium, QR và ảnh giao diện đăng nhập.
- Khi nâng phiên bản, trình duyệt tải tài nguyên mới; khi không đổi, trình duyệt dùng lại cache.

## File đã chỉnh sửa

- `app.py`
  - Khoảng dòng 65: tăng phiên bản.
  - Khoảng dòng 3750–3811: API trạng thái phòng trả fragment động và chống lỗi render.
  - Khoảng dòng 4173–4275: xử lý API chat, phản hồi dừng polling và gửi chat AJAX.
- `static/js/pes_polling.js`
  - Khoảng dòng 1–275: registry poller/request, khóa in-flight, AbortController, gỡ listener và dừng poller cũ.
- `templates/base.html`
  - Khoảng dòng 9–23: version CSS/JS.
  - Khoảng dòng 337–373: khóa request lời mời.
  - Khoảng dòng 849–881: một poller lời mời và dừng poller cũ.
- `templates/room_detail.html`
  - Khoảng dòng 138–500: một polling trạng thái, cập nhật fragment, dừng request khi rời trang.
  - Khoảng dòng 500–708: một polling chat, khóa tải/gửi chat và gửi AJAX.
  - Khoảng dòng 844–905: dừng realtime trước khi xác nhận thoát.
- `templates/_room_live_content.html`
  - Khoảng dòng 1–288: import macro avatar, version ảnh Rank/VS và form chat động.
- `templates/_rank_macros.html`
  - Khoảng dòng 1–8: version ảnh Rank dùng chung.
- `static/style.css`
  - Khoảng dòng 419 và 1237: version ảnh nền giao diện đăng nhập.
- `templates/guide.html`
  - Khoảng dòng 13 và 90: version QR và thẻ Rank.
- `templates/public_ranking.html`
  - Khoảng dòng 55: version ảnh podium.
- `templates/ranking.html`
  - Khoảng dòng 16: version ảnh podium.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse 25 template Jinja: đạt.
- Render toàn bộ `room_detail.html` với fragment động: đạt.
- Kiểm tra cú pháp toàn bộ JavaScript nội tuyến sau render: đạt.
- `node --check static/js/pes_polling.js`: đạt.
- `node --check static/js/session-timeout.js`: đạt.
- Kiểm tra khóa request: ba lệnh cùng khóa chỉ chạy task một lần.
- Kiểm tra thay poller cùng khóa: listener cũ được gỡ, không tích lũy.
- Số route decorator trước/sau: giữ nguyên 100; không thêm hoặc mất route.
- Số điểm gọi trạng thái phòng: 1.
- Số điểm gọi chat phòng: 1.
- Số điểm gọi lời mời chờ: 1.
- `location.reload()` trong `room_detail.html`: 0.
- Ảnh tĩnh trong template chưa có version: 0.

## Cài đặt

Chép đè các file trong gói này lên nhánh `Collap_V1.13.3lv2`. Không áp dụng lên hai nhánh song song khác nếu chưa đối chiếu riêng.
