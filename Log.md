# Collap_V1.13.1 – Chia sẻ link tham gia phòng đấu

- Ngày giờ: 18/07/2026 13:45 (Asia/Bangkok)
- Bản nền đối chiếu: `Collap_V1.13.0`
- Loại phát hành: Bản full, không bọc thư mục cha khi đóng ZIP.

## Nội dung nâng cấp

1. Thêm nút **Chia sẻ phòng** ở góc phải tiêu đề phòng khi phòng đang trống và ở trạng thái `waiting_ready`.
2. Nút tự copy link tham gia phòng; có thông báo **Đã copy link** và phương án copy dự phòng cho trình duyệt không hỗ trợ Clipboard API.
3. Thêm route `GET /room/join/<room_id>` để người nhận link tham gia trực tiếp vào vị trí khách.
4. Người chưa đăng nhập được đưa tới trang Login và tự quay lại đúng phòng sau khi đăng nhập.
5. Người dùng mật khẩu tạm vẫn quay lại link phòng sau khi hoàn thành bước đổi mật khẩu bắt buộc.
6. Chỉ cho tham gia khi phòng còn trống, chưa bắt đầu, người tham gia không có phòng/trận khác và không ở thời gian cooldown.
7. Dùng cập nhật có điều kiện `status = waiting_ready` và `guest_user_id IS NULL` để ngăn hai người cùng chiếm vị trí khách.
8. Khi link chia sẻ được dùng thành công, lời mời riêng cũ gắn với phòng được hủy để tránh người thứ ba chấp nhận vào cùng phòng.
9. Xóa cache phòng/lời mời sau khi tham gia để máy chủ và máy khách nhìn thấy người mới ngay ở lần kiểm tra tiếp theo.
10. Không thêm bảng/cột Supabase và không thay đổi dữ liệu lịch sử, RP hoặc thời gian trận.

## File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | dòng 65 | Tăng phiên bản thành `Collap_V1.13.1` |
| `app.py` | dòng 3906–3914 | Quay lại link phòng sau đăng nhập |
| `app.py` | dòng 3991–4001 | Quay lại link phòng sau đổi mật khẩu bắt buộc |
| `app.py` | vùng route Rooms, khoảng 5045–5167 | Route tham gia phòng qua link, kiểm tra điều kiện và khóa tranh chấp vị trí khách |
| `templates/room_detail.html` | dòng 35–60 | Nút chia sẻ/copy link tại thanh tiêu đề phòng |
| `templates/room_detail.html` | khoảng dòng 424–477 | Clipboard API, fallback copy và trạng thái giao diện |
| `static/style.css` | khoảng dòng 3075–3090 và 3151–3158 | Giao diện desktop/mobile của nút chia sẻ |
| `Log.md` | toàn file | Nhật ký phiên bản |

## Luồng sử dụng

1. Chủ phòng tạo phòng và chưa có khách.
2. Bấm **Chia sẻ phòng – Copy link tham gia**.
3. Gửi link cho người muốn thi đấu.
4. Người nhận mở link:
   - Đã đăng nhập: hệ thống kiểm tra và đưa thẳng vào phòng.
   - Chưa đăng nhập: đăng nhập xong sẽ tự quay lại và tham gia phòng.
5. Khách bấm **Sẵn Sàng**, sau đó chủ phòng quay đội như luồng hiện tại.

## Tình huống được chặn

- Phòng đã đủ hai người.
- Phòng đã bắt đầu, đã kết thúc, bị hủy hoặc đang tranh chấp.
- Người mở link đang có phòng/trận khác.
- Chủ phòng đang ở một trận/phòng khác do dữ liệu cũ không đồng bộ.
- Hai người bấm link gần như đồng thời: chỉ người cập nhật thành công đầu tiên được vào.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`
- Parse toàn bộ template Jinja.
- Kiểm tra route Flask trùng URL + HTTP method.
- Kiểm tra ZIP root, không có `__pycache__`/`.pyc`.
- Kiểm tra khác biệt với `Collap_V1.13.0`: chỉ thay `app.py`, `templates/room_detail.html`, `static/style.css`, `Log.md`.

## Cài đặt

Giải nén ZIP, chép đè toàn bộ file vào repository, Commit/Push và Redeploy Vercel. Không cần chạy SQL.
