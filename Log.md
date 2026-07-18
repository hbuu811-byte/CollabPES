# Collap_V1.13.2 – Tách module Admin, phòng đấu, RP và sửa điểm

- Ngày giờ: 18/07/2026 14:03 (Asia/Bangkok)
- Bản nền đối chiếu: `Collap_V1.13.1`
- Loại phát hành: Bản full, ZIP không bọc thư mục cha.

## Mục tiêu

Tách các vùng có tần suất nâng cấp cao khỏi `app.py`, giúp sửa đúng một nhóm chức năng mà không ghi đè hoặc làm chồng chéo luồng Admin, phòng đấu, RP và sửa điểm.

## Kết quả phân tách

- `app.py` giảm từ khoảng **8.413 dòng xuống 5.108 dòng**.
- Giữ nguyên **100 route Flask**, tên endpoint, URL và HTTP method so với `Collap_V1.13.1`.
- Tách route phòng thành 4 module nhỏ.
- Tách route Admin thành 6 module nhỏ.
- Tách nghiệp vụ sửa điểm/RP thành 4 service theo thứ tự dependency.
- Giữ nguyên `modules/rp_formula.py`, `modules/rp_engine.py`, `modules/admin_match_service.py` và `modules/admin_ranking_rebuild.py` làm nguồn logic chuyên biệt.

## File đã sửa hoặc tạo

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | dòng 1–65; 5033–5108 | Nâng version, bỏ các khối route lớn và đăng ký các module theo thứ tự dependency |
| `modules/room_access_routes.py` | toàn file, khoảng 226 dòng | Danh sách phòng, tham gia link chia sẻ, xem và rời phòng |
| `modules/room_rematch_routes.py` | toàn file, khoảng 249 dòng | Bỏ cuộc và đá lại |
| `modules/room_team_routes.py` | toàn file, khoảng 271 dòng | Quay đội, giao hữu và trạng thái sẵn sàng |
| `modules/room_result_routes.py` | toàn file, khoảng 302 dòng | Nhập, xác nhận và tranh chấp kết quả |
| `modules/match_history_routes.py` | toàn file, khoảng 80 dòng | Trang lịch sử trận |
| `modules/ranking_lock_service.py` | toàn file, khoảng 168 dòng | Khóa phát lại BXH và so sánh trạng thái |
| `modules/match_result_service.py` | toàn file, khoảng 391 dòng | Cộng/trừ RP, W-D-L, streak, tranh chấp và hoàn tác |
| `modules/ranking_rebuild_service.py` | toàn file, khoảng 146 dòng | Phát lại lịch sử sau khi Admin sửa trận |
| `modules/data_cleanup_service.py` | toàn file, khoảng 79 dòng | Xóa dữ liệu liên quan theo thứ tự an toàn |
| `modules/admin_system_routes.py` | toàn file, khoảng 342 dòng | Bảo trì, công tắc, backup RP và chuyển owner |
| `modules/admin_dashboard_routes.py` | toàn file, khoảng 95 dòng | Trang tổng quan Admin |
| `modules/admin_account_routes.py` | toàn file, khoảng 570 dòng | Tài khoản, CSV, duyệt/khóa và phân quyền |
| `modules/admin_match_routes.py` | toàn file, khoảng 294 dòng | Tranh chấp và sửa tỷ số/trạng thái |
| `modules/admin_player_routes.py` | toàn file, khoảng 145 dòng | Sửa/reset/xóa người chơi |
| `modules/admin_data_routes.py` | toàn file, khoảng 135 dòng | Xóa trận, phòng và lời mời |
| `docs/KIEN_TRUC_MODULE_COLLAP_V1.13.2.md` | toàn file | Sơ đồ file cần sửa cho từng tính năng |
| `Log.md` | đầu file | Nhật ký phiên bản mới, giữ lịch sử cũ bên dưới |

## Nguyên tắc bảo toàn logic

1. Không đổi URL hoặc endpoint Flask.
2. Không đổi schema Supabase.
3. Không đổi công thức RP.
4. Không đổi `created_at` của trận.
5. Route phòng và Admin dùng chung service kết quả/RP.
6. Mọi module được đăng ký sau khi toàn bộ helper chung đã sẵn sàng, tránh import vòng.
7. `redirect_admin()` được giữ làm helper dùng chung thay vì sao chép ở nhiều module.

## Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Import `app.py` trong môi trường không có Supabase: đạt.
- So sánh route map với `Collap_V1.13.1`: **100/100 route giống hoàn toàn**.
- Không có URL + HTTP method bị trùng.
- Parse 24 template Jinja: đạt.
- `test_rp_engine.py`: đạt với `RP_V1.12.0`.
- Không cần chạy SQL.

## Hướng dẫn nâng cấp sau này

Xem `docs/KIEN_TRUC_MODULE_COLLAP_V1.13.2.md` để biết chính xác file cần sửa theo từng tính năng. Không tiếp tục dồn route Admin, phòng đấu hoặc công thức RP vào `app.py`.

---

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
