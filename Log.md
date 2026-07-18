# Log — Collap_V1.13.0

- **Ngày giờ:** 18/07/2026 13:24, múi giờ Asia/Bangkok (UTC+7)
- **Loại phát hành:** Bản full, file nằm ngay ở thư mục gốc ZIP, không bọc folder cha
- **Phiên bản nguồn đối chiếu:**
  - `PES_Arena_V1.13.13-v4.9.1_Admin_Doi_Trang_Thai_Tinh_Lai_Lich_Su.zip`
  - `PES_Arena_V1.13.13-v4.9.2_Sua_Hien_Thi_Ben_Thang_Ben_Thua.zip`
  - Bản full PES Arena/Collaboration gần nhất đang có trong phiên làm việc

## 1. Nguyên nhân lỗi Vercel 500

Hai gói v4.9.1 và v4.9.2 là gói vá rời nhưng `app.py` trong đó đã import thêm các module:

- `modules.admin_match_service`
- `modules.admin_ranking_rebuild`
- `modules.system_feature_service`
- `modules.session_runtime_service`

Gói v4.9.1 chỉ mang theo một phần module; gói v4.9.2 không mang theo các module backend. Khi chép `app.py` lên repository mà thiếu module, Vercel dừng ngay ở bước `could not import "app.py"` và mọi URL trả về HTTP 500.

## 2. Nội dung đã sửa

### 2.1. Sửa lỗi import làm sập toàn bộ website

- Đóng lại dưới dạng **bản full**.
- Bổ sung đầy đủ toàn bộ module mà `app.py` đang import.
- Giữ `modules/__init__.py` để Python nhận diện package `modules` ổn định trên Vercel.
- Bổ sung template và JavaScript phụ thuộc của bảo trì máy chủ, thông báo và timeout phiên.

### 2.2. Admin sửa tỷ số và trạng thái trận

- Admin có quyền phù hợp được đổi tỷ số/trạng thái trận.
- Trận confirmed bị sửa hoặc chuyển trạng thái sẽ phát lại lịch sử theo thứ tự thời gian gốc.
- Tính lại RP, thắng, hòa, thua, tổng trận, bàn thắng, bàn thua, `streak` và `loss_streak`.
- Giữ thành tích import/legacy bằng cách suy ra mốc thống kê gốc trước khi phát lại.
- Trận hủy không ghi `NULL` vào `delta1/delta2`; dùng `0` để tương thích cột Supabase `NOT NULL`.

### 2.3. Không thay đổi thời gian trận

- `created_at` chỉ được dùng để sắp xếp lịch sử.
- Mọi payload cập nhật đều loại bỏ `created_at`.
- Chỉ cập nhật `updated_at` khi cần.

### 2.4. Khóa luồng an toàn

- Dùng khóa toàn hệ thống khi Admin phát lại BXH.
- Chặn hai Admin sửa/tính lại cùng lúc.
- Luồng người chơi xác nhận kết quả kiểm tra khóa để không cộng RP đồng thời với luồng Admin.
- So sánh trạng thái trận mới nhất trước khi ghi để tránh ghi đè dữ liệu vừa đổi.
- Khóa có thời hạn và luôn được giải phóng trong `finally`.

### 2.5. Sửa hiển thị bên thắng/bên thua

- Hồ sơ và lịch sử cá nhân luôn đặt người đang xem ở bên trái.
- Tên, avatar, CLB, tỷ số, delta RP và nhãn THẮNG/THUA dùng cùng một thứ tự trái/phải.
- Lịch sử toàn hệ thống vẫn giữ thứ tự gốc `player1 - player2`.
- Người thắng hiển thị được suy ra từ tỷ số confirmed, tránh lệch do `winner_id` cũ.
- Hỗ trợ tỷ số/delta Supabase trả về dạng số hoặc chuỗi.

## 3. File đã chỉnh sửa hoặc bổ sung

| File | Khoảng dòng gần đúng | Nội dung |
|---|---:|---|
| `app.py` | 34–55 | Import đầy đủ module backend phụ thuộc |
| `app.py` | 65 | Đặt phiên bản `Collap_V1.13.0` |
| `app.py` | 1951–2124 | Chuẩn hóa tỷ số, thứ tự trái/phải, người thắng/người thua ở Lịch sử và Hồ sơ |
| `app.py` | 3439–3653 | Timeout phiên và luồng kiểm tra phòng đang thi đấu |
| `app.py` | 6055–6117 | Khóa phát lại BXH toàn hệ thống |
| `app.py` | 6536–6653 | Phát lại RP/thống kê theo `created_at` gốc và rollback an toàn |
| `app.py` | 7786–7903 | Admin cập nhật tỷ số/trạng thái, kiểm tra quyền và giữ nguyên mốc thời gian |
| `app.py` | 7907–7954 | Admin hủy trận và tính lại lịch sử; delta trung gian dùng `0` |
| `modules/admin_match_service.py` | 1–71 | Chuẩn hóa tỷ số và phát hiện thay đổi |
| `modules/admin_ranking_rebuild.py` | 1–326 | Tính mốc legacy, phát lại RP/W-D-L/streak và không ghi `created_at` |
| `modules/session_runtime_service.py` | 1–55 | Quyết định timeout phiên và bảo vệ người đang trong trận |
| `modules/system_feature_service.py` | 1–12 | Điều hướng sau đăng nhập và bật/tắt Dashboard |
| `static/js/session-timeout.js` | 1–132 | Timeout phía trình duyệt, không tăng polling liên tục |
| `templates/admin.html` | 1–677 | Giao diện sửa tỷ số/trạng thái và phân quyền Admin |
| `templates/matches.html` | 1–63 | Hiển thị đúng bên trái/phải trong lịch sử |
| `templates/profile.html` | 1–234 | Hiển thị đúng chủ hồ sơ, đối thủ và kết quả |
| `templates/base.html` | 1–867 | Nạp phụ thuộc timeout/thông báo hiện hành |
| `templates/maintenance.html` | toàn file | Trang bảo trì máy chủ |
| `templates/admin_login.html` | toàn file | Đăng nhập Admin khi máy chủ bảo trì |
| `templates/notifications.html` | toàn file | Trang thông báo cá nhân |
| `static/style.css` | toàn file | CSS tương ứng với các template hiện hành |

## 4. Kiểm tra kỹ thuật đã thực hiện

- `python -m py_compile app.py modules/*.py`: **Đạt**.
- Import trực tiếp `app.py` với đầy đủ dependency: **Đạt**.
- Phiên bản đọc được sau import: `Collap_V1.13.0`.
- Flask đăng ký 99 route: **Đạt**.
- Route trùng URL + HTTP method: **0**.
- Parse 24 template Jinja: **0 lỗi**.
- Test RP Engine `RP_V1.12.0`: **Đạt**.
- Test module phát lại BXH/Admin: **Đạt**.
- Test người chơi là `player2`, tỷ số `2-5`, `winner_id` cũ bị sai: giao diện vẫn hiện đúng `5-2`, THẮNG, đúng tên và đúng delta RP: **Đạt**.
- ZIP phát hành không chứa `__pycache__`, `.pyc` hoặc file backup.

## 5. Cách triển khai

1. Giải nén `Collap_V1.13.0.zip`.
2. Chép toàn bộ nội dung bên trong vào **thư mục gốc repository**, nơi có `app.py` và `vercel.json`.
3. Cho phép ghi đè các file trùng tên.
4. Commit, Push và Redeploy trên Vercel.
5. Không cần chạy SQL mới.

Nên triển khai trên nhánh Test trước, kiểm tra `/`, `/login`, `/admin-login`, `/matches`, `/profile/<id>` và thao tác Admin sửa một trận confirmed trước khi gộp vào nhánh chính.
