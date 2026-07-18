# Collap_V1.13.3a — Giới hạn Admin quản lý trạng thái và thông báo 20/7 ngày

- **Phiên bản nền:** `Collap_V1.13.2`
- **Ngày giờ:** 18/07/2026 16:46 — Asia/Bangkok
- **Kiểu phát hành:** Gói file cần chép đè, không phải bản full.
- **SQL Supabase:** Không bắt buộc và không nằm trong ZIP này. File SQL tùy chọn được lưu riêng để nâng cấp sau.

## 1. Phạm vi Admin quản lý trận

Admin không còn được nhập hoặc sửa tỷ số tại bảng **🎮 Quản lý trận đấu gần đây**.

Admin chỉ được thực hiện hai thay đổi trạng thái:

- `Đã xác nhận` (`confirmed`) — yêu cầu quyền `matches_confirm` và trận đã có đủ hai tỷ số.
- `Đã hủy` (`cancelled`) — yêu cầu quyền `matches_cancel`.

Các trạng thái trung gian như `playing`, `waiting_confirm` và `disputed` không thể được chọn từ bảng này.

Khi trận đi vào hoặc rời trạng thái `confirmed`, hệ thống vẫn:

- Giữ nguyên tỷ số đã có.
- Giữ nguyên `created_at`.
- Phát lại lịch sử theo `created_at`, sau đó theo `id`.
- Tính lại RP, W-D-L, bàn thắng/bàn thua, `streak` và `loss_streak`.
- Dùng `delta1 = 0`, `delta2 = 0` cho trận bị hủy; không ghi `NULL`.

Xóa trực tiếp trận đấu đã được tắt ở cả giao diện và endpoint cũ. Admin cần chuyển trận sang **Đã hủy** thay vì xóa dữ liệu lịch sử.

## 2. Thông báo người chơi

- Mỗi người chỉ xem tối đa **20 thông báo mới nhất**.
- Thông báo quá **7 ngày** không được hiển thị và được xóa khỏi bảng khi:
  - người chơi mở trang Thông báo; hoặc
  - hệ thống tạo thông báo mới cho người đó.
- Không thêm polling và không cần trigger Supabase.
- Bỏ phân trang vì dữ liệu hiển thị tối đa 20 mục.

## 3. File đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | 65 | Nâng phiên bản thành `Collap_V1.13.3a`. |
| `app.py` | 2192 | Tách logic thông báo sang `modules/notification_service.py`. |
| `app.py` | 3486–3501 | Trang thông báo cố định tối đa 20 mục, hạn 7 ngày. |
| `app.py` | 4968–4984 | Nạp dịch vụ thông báo trước các module nghiệp vụ khác. |
| `modules/notification_service.py` | 1–176 | Tạo, đọc, xóa thông báo quá hạn và cắt danh sách còn 20 mục. |
| `modules/admin_ranking_rebuild.py` | 233–245 | Trận rời `confirmed` dùng delta `0`, không ghi `NULL`. |
| `modules/admin_match_routes.py` | 65–183 | Chỉ cho đổi trạng thái `confirmed/cancelled`; bỏ hoàn toàn việc nhận tỷ số từ form. |
| `modules/admin_data_routes.py` | 9–21 | Khóa xóa trực tiếp trận; giữ endpoint cũ để không làm mất route. |
| `templates/admin.html` | 368–417 | Tỷ số chuyển thành chỉ đọc; chỉ còn lựa chọn Đã xác nhận/Đã hủy; bỏ nút Xóa. |
| `templates/notifications.html` | 1–45 | Thông báo giới hạn 20 mục/7 ngày và bỏ phân trang. |

## 4. File SQL để nâng cấp sau

File sau được phát hành riêng, không nằm trong ZIP và **không cần chạy cho Collap_V1.13.3a**:

`Collap_V1.13.3a_Supabase_Nang_Cap_Sau.sql`

File này chỉ lưu các đề xuất tương lai như constraint/index, bảng audit và trigger dọn thông báo. Hãy backup và kiểm tra trên database Test trước khi chạy.

## 5. Kiểm tra kỹ thuật

- `python -m py_compile app.py modules/*.py`: đạt.
- Parse 24 template Jinja: đạt.
- Import `app.py`: đạt.
- Phiên bản import: `Collap_V1.13.3a`.
- Route Flask: đủ `100/100`, không mất hoặc thêm route so với `Collap_V1.13.2`.
- Kiểm tra form gửi `score1=99`, `score2=0`: backend bỏ qua, không đưa tỷ số vào payload.
- Kiểm tra `waiting_confirm → confirmed`: dùng nguyên tỷ số đang lưu và gọi phát lại BXH.
- Kiểm tra `confirmed → cancelled`: delta về `0`, RP và thống kê trở lại mốc trước trận.
- Kiểm tra thông báo: 3 mục quá 7 ngày và 25 mục còn hạn được dọn còn đúng 20 mục mới nhất.
- ZIP không có thư mục cha, không có SQL, không có `__pycache__` hoặc `.pyc`.

## 6. Cài đặt

1. Giữ nguyên dự án `Collap_V1.13.2`.
2. Giải nén `Collap_V1.13.3a.zip`.
3. Chép đè các file đúng đường dẫn vào repository.
4. Không chạy SQL ở thời điểm này.
5. Commit, Push và triển khai trên nhánh Test trước.
