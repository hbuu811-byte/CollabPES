# Collap_V1.13.3l — Tối ưu polling, reload phòng và cache static

- **Ngày giờ:** 19/07/2026 00:03 — múi giờ Asia/Bangkok.
- **Bản nền:** `Collap_V1.13.3k`.
- **Phạm vi:** chỉ sửa các file liên quan đến polling, cập nhật phòng và cache; không sửa RP, Supabase, lịch sử bỏ cuộc hoặc quyền Admin.

## 1. Kết quả đối chiếu báo cáo

Một số đề xuất trong báo cáo đã tồn tại ở bản nền và không được viết chồng lại:

- `/api/room/<id>/state` đã có biến khóa request đang chạy.
- Polling phòng đã dùng chuỗi `setTimeout`, không dùng nhiều `setInterval` trạng thái phòng.
- Ô tỷ số đã có bản nháp trong `sessionStorage`.
- `pes_polling.js` đã tự dừng request khi tab ẩn.

Các phần còn thiếu hoặc chưa triệt để đã được sửa trong bản này.

## 2. Phòng đấu không reload toàn trang khi trạng thái đổi

### Trước

Khi `state_key` thay đổi, template gọi:

```javascript
window.location.reload();
```

Điều này làm tải lại HTML, CSS, JS và ảnh, gây nháy màn hình và tạo nhiều request bị hủy khi chuyển trạng thái nhanh.

### Sau

- Gọi `/api/room/<id>/state` để phát hiện thay đổi.
- Khi có thay đổi, chỉ tải HTML phòng mới bằng `fetch`.
- Chỉ thay khối `#roomLiveShell` trong DOM.
- Không tải lại thanh menu, CSS, JavaScript và phần khung ứng dụng.
- Tự gắn lại sự kiện cho:
  - Copy link phòng.
  - Ô nhập tỷ số.
  - Modal thoát/bỏ cuộc.
  - Các nút thao tác trong phòng.
  - Chat phòng.

Các thao tác sau được gửi bằng AJAX và cập nhật riêng phần phòng:

- Sẵn sàng/Hủy sẵn sàng.
- Quay đội.
- Nhập kết quả.
- Xác nhận kết quả.
- Đá tiếp.
- Quay lại/kết thúc giao hữu.
- Chat phòng.

Thoát phòng, bỏ cuộc hoặc thao tác cần chuyển sang trang khác vẫn điều hướng bình thường.

## 3. Chỉ một request trạng thái phòng tại một thời điểm

- Giữ khóa `roomStateRequestInFlight`.
- Không tạo request mới khi:
  - Request `/state` trước chưa xong.
  - Một thao tác POST trong phòng đang chạy.
  - Phần giao diện phòng đang được làm mới.
- Bỏ `AbortController` khỏi polling trạng thái phòng để tránh tự tạo `ERR_ABORTED` khi rời trang.
- Thêm `window.PESRoomStateController`; nếu script bị khởi tạo lại thì vòng cũ được dừng trước.
- Khi `pagehide`, timer được dừng nhưng không hủy một request bằng AbortController.

## 4. Bảo vệ ô nhập tỷ số

- Polling không còn bị dừng toàn bộ chỉ vì người dùng đã nhập tỷ số.
- Bản nháp tỷ số được giữ trong `sessionStorage`.
- Nếu giao diện phòng cập nhật trong lúc đang nhập, bản nháp được khôi phục vào ô mới.
- Chỉ xóa bản nháp sau khi server nhận thao tác nhập kết quả thành công.
- Không còn tình trạng state mới ghi đè ô đang nhập về `0`.

## 5. Chu kỳ polling phòng

| Trạng thái | Chu kỳ mới |
|---|---:|
| Chờ sẵn sàng | khoảng 3 giây |
| Đang thi đấu — phía khách | khoảng 5 giây |
| Đang thi đấu — phía chủ | khoảng 12 giây |
| Chờ xác nhận kết quả | khoảng 2 giây |
| Đã xác nhận/chờ đá tiếp | khoảng 5 giây |
| Tab bị ẩn | khoảng 60 giây |

Khi quay lại tab, hệ thống kiểm tra ngay một lần.

## 6. `pes_polling.js` chỉ còn một poller cho mỗi chức năng

Thêm registry theo `key`:

- `heartbeat`
- `pending-invites`
- `active-room`
- `lobby-chat`
- `announcement`
- `online-count`

Nếu một poller cùng key được tạo lại, poller cũ bị dừng trước. Khi rời trang, toàn bộ poller được dọn.

## 7. Polling ngoài phòng

| API | Cách chạy mới |
|---|---|
| `/api/invites/pending` | 15 giây tại Players/BXH, 20 giây ở trang khác cần thiết |
| Trong phòng đấu | Không polling lời mời |
| Trang Lịch sử | Không polling lời mời hoặc active-room |
| Trang Hướng dẫn | Không polling lời mời hoặc active-room |
| `/heartbeat` | khoảng 60 giây, dừng khi tab ẩn |
| `/api/announcement/current` | khoảng 120 giây, dừng khi tab ẩn |
| `/api/session/activity` | Chỉ gửi theo thao tác người dùng, giữ giới hạn cấu hình 300 giây và khóa request chồng |

## 8. Cache CSS, JS và ảnh static

- URL CSS/JS dùng `APP_VERSION`, nên mỗi phiên bản mới tự đổi URL cache.
- Thêm header:

```text
Cache-Control: public, max-age=604800, stale-while-revalidate=86400
```

- Áp dụng trong cả Flask `after_request` và `vercel.json`.
- Không cache lâu API trạng thái phòng.

## 9. File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | dòng 65; 1472–1490 | Tăng phiên bản; cache static |
| `static/js/pes_polling.js` | toàn file | Registry singleton, khóa in-flight, dọn poller |
| `static/js/session-timeout.js` | dòng 3–145 | Chặn khởi tạo hai lần; khóa request activity |
| `templates/base.html` | dòng 9–23; 790–885 | Version static; polling theo từng trang và key |
| `templates/room_detail.html` | dòng 4; khoảng 540–1190 | Soft refresh phòng, AJAX form, giữ bản nháp tỷ số, một vòng state polling |
| `templates/maintenance.html` | dòng 7 | Version URL CSS |
| `templates/public_ranking.html` | dòng 10 | Version URL CSS |
| `vercel.json` | toàn file | Header cache `/static/*` |

## 10. Kiểm tra đã thực hiện

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse 24 template Jinja: đạt.
- `node --check` cho `pes_polling.js`: đạt.
- `node --check` cho `session-timeout.js`: đạt.
- Kiểm tra cú pháp bốn khối JavaScript trong `room_detail.html`: đạt.
- Test tạo hai poller cùng key: registry chỉ giữ một poller.
- `vercel.json`: JSON hợp lệ.
- Không còn `location.reload()` trong template phòng.
- Không thêm SQL Supabase.

## 11. Lưu ý kiểm thử thực tế

Sau khi deploy nhánh test, nên dùng hai trình duyệt và kiểm tra:

1. Khách vào phòng và bấm Sẵn Sàng.
2. Chủ quay đội.
3. Chủ nhập tỷ số trong khi polling vẫn chạy.
4. Khách nhận màn hình xác nhận mà không cần F5.
5. Khách xác nhận.
6. Hai bên bấm Đá tiếp và thi đấu thêm 2–3 trận.
7. Chuyển tab trong 60 giây rồi quay lại.
8. Dùng Network lọc `state`, `pending`, `activity`, `heartbeat` để xác nhận không chạy chồng.
