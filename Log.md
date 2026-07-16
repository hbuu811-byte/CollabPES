# PES Arena V1.13.8 – Hoàn Tất Trận & Tự Hủy Phòng Quá Hạn

## Nội dung nâng cấp

### 1. Bỏ thông báo kỹ thuật khi quay đội
- `app.py`, route quay đội xếp hạng: bỏ nội dung `Tạo tự động bằng Smart Tier Random. Power score ... Host XP ...` khỏi trường `matches.note`.
- Trận mới không còn hiển thị dòng kỹ thuật này trong lịch sử/Profile.
- Các trận cũ đã lưu nội dung trong Supabase không tự động bị sửa.

### 2. Buộc quay lại phòng khi trận chưa hoàn tất
- `app.py`, API `/api/active-room`: chỉ bật `auto_redirect` khi phòng ở trạng thái `playing`, `friendly_playing` hoặc `waiting_result_confirm` và đã có đủ hai người.
- `templates/base.html`: kiểm tra phòng mỗi 5 giây trên mọi trang; khi chuyển lại tab trình duyệt sẽ kiểm tra ngay và đưa người chơi về phòng.
- Phòng trống hoặc mới chờ sẵn sàng không ép chuyển trang.

### 3. Tự đóng phòng theo thời gian không hoạt động
- Phòng `waiting_ready`: tự hủy sau 30 phút không có thao tác có ý nghĩa; không trừ RP.
- Phòng đã quay đội (`playing`/`friendly_playing`): giới hạn 60 phút không hoạt động.
- Phòng `waiting_result_confirm`: giới hạn 60 phút chờ xác nhận.

### 4. Phạt bỏ dở theo vai trò
- `playing` xếp hạng quá 60 phút: chủ phòng bị tính một trận thua và trừ ngẫu nhiên 22–25 RP.
- `waiting_result_confirm` quá 60 phút: khách bị tính một trận thua và trừ ngẫu nhiên 22–25 RP.
- Đối thủ không được cộng RP.
- Cơ chế cập nhật có điều kiện theo trạng thái phòng để tránh hai request cùng trừ điểm hai lần.
- Mức RP thực tế được lưu vào `matches.delta1/delta2` và thông báo cho người bị phạt.

## File đã sửa
- `app.py`: phiên bản, timeout 30/60 phút, phạt 22–25 RP, API ép quay về phòng, bỏ ghi chú Smart Tier.
- `templates/base.html`: tự quay về phòng trên toàn hệ thống và kiểm tra lại khi người dùng trở về tab.
- `Log.md`: ghi thay đổi V1.13.8.

## Cài đặt
1. Giải nén ZIP và chép đè toàn bộ file vào repository.
2. Commit, Push và Redeploy Vercel.
3. Không cần chạy SQL Supabase.
4. Test trên database Test trước khi đưa lên Production.

## Kịch bản test
1. Tạo phòng nhưng không có hoạt động: chỉnh tạm timeout nhỏ trên Test hoặc chờ đủ 30 phút; phòng phải chuyển `cancelled`, RP không đổi.
2. Đủ hai người, quay đội, không nhập tỷ số: sau 60 phút chủ phòng mất 22–25 RP.
3. Chủ nhập tỷ số, khách không xác nhận: sau 60 phút khách mất 22–25 RP.
4. Đang `playing` hoặc `waiting_result_confirm`, mở Dashboard/BXH/tab khác: trong tối đa 5 giây bị đưa lại phòng.
5. Phòng chỉ `waiting_ready`: vẫn có thể xem trang khác, không bị ép quay lại.
# PES Arena V1.13.7 – Tách Công Thức RP & Loại Bỏ Fallback -20

## Thay đổi chính
- Tạo `modules/rp_formula.py`: nơi duy nhất chứa phiên bản và toàn bộ thông số công thức RP.
- `modules/rp_engine.py` chỉ còn logic tính toán; không chứa số cấu hình rải rác.
- Loại bỏ hoàn toàn fallback `BASE_LOSS_POINTS = -20` trong luồng xác nhận trận.
- Nếu engine trả RP thua bằng 0/sai dấu, hệ thống dừng và báo lỗi; không tự biến thành -20.
- Mỗi trận lưu `rp_formula_version = RP_V1.12.0` và `rp_details` gồm nguồn, công thức, seed và delta.
- Seed ngẫu nhiên gắn với cả phiên bản công thức và `match_id`, bảo đảm tính lại ổn định.

## File sửa
- `modules/rp_formula.py`: file mới, toàn bộ cấu hình công thức.
- `modules/rp_engine.py`: logic tính và `validate_deltas`.
- `app.py`: dùng version/seed mới, bỏ fallback -20, lưu chi tiết RP.
- `test_rp_engine.py`: kiểm thử delta thua bằng 0 phải bị từ chối.

## Cài đặt
Không cần chạy SQL. Chép đè toàn bộ file, Commit, Push và Redeploy.

---

# PES Arena V1.13.6 – Sửa lỗi NOT NULL delta khi sửa và tính lại trận

## Lỗi đã sửa

- Sửa lỗi Supabase `23502`: cột `matches.delta1`/`delta2` là `NOT NULL` nhưng code ghi `null` khi chuẩn bị sửa trận.
- Khi tạm đưa trận về `waiting_confirm`, hệ thống dùng `delta1 = 0`, `delta2 = 0` làm giá trị trung gian hợp lệ.
- Áp dụng cùng nguyên tắc cho công cụ tính lại RP và thao tác hủy phòng/trận.
- Sau khi tính xong, `apply_match_result()` vẫn ghi đè bằng RP thật; số 0 chỉ tồn tại trong giai đoạn chuẩn bị.

## File và vị trí sửa

- `app.py` dòng gần 57: nâng phiên bản lên `V1.13.6`.
- `app.py` hàm `recalculate_rank_history`: thay delta trung gian `None` bằng `0`.
- `app.py` route `admin_update_match_result`: thay delta trung gian `None` bằng `0`.
- `app.py` route `admin_cancel_room`: trận bị hủy lưu delta bằng `0` thay vì `null`.

## Cài đặt

Không cần chạy SQL. Chép đè code, commit/push và redeploy.

---

# PES Arena V1.13.5 – Bộ Công Cụ Tính RP

## Thay đổi lớn

- Bỏ tab Backup/Restore toàn bộ Supabase.
- Gộp Backup RP, Restore RP và Tính lại RP vào tab `📈 Bộ Công Cụ Tính RP`.
- RP Backup chỉ lưu các trường RP, thống kê, chuỗi và delta trận.
- Restore RP không xóa hoặc tạo tài khoản/trận; không sửa tỷ số.
- Tính lại RP dùng ID trận làm hạt ngẫu nhiên cố định để kết quả ổn định khi chạy lại.
- Sửa lỗi tính lại RP đọc nhầm các trận tương lai khi tính chuỗi thua: toàn bộ trận hợp lệ được chuyển khỏi `confirmed` trước khi chạy tuần tự.
- Thêm quyền `rp_backup_restore`; bỏ `backup_manage` khỏi nhóm Hệ thống.

## File và vị trí sửa

- `app.py` dòng gần 57: phiên bản V1.13.5.
- `app.py` vùng `ADMIN_PERMISSION_GROUPS`: quyền `rp_backup_restore`.
- `app.py` hàm `calculate_deltas` và `apply_match_result`: hạt ngẫu nhiên cố định theo ID trận.
- `app.py` hàm `recalculate_rank_history`: chuẩn bị toàn bộ lịch sử rồi mới tính tuần tự.
- `app.py` vùng route `/admin/rp/backup/*`: Backup và Restore RP.
- `templates/admin.html` tab Công cụ RP: giao diện ba công cụ.
- `static/style.css` cuối file: bố cục Bộ Công Cụ RP.
- `docs/HUONG_DAN_BO_CONG_CU_RP_V1.13.5.md`: hướng dẫn và công thức.

## Cài đặt

Không cần chạy SQL mới. Chép đè code, commit/push và redeploy. Trước lần tính lại đầu tiên trên Production, hãy tải một file Backup RP.

# PES Arena V1.13.4 — Khôi phục dữ liệu Supabase

## Nâng cấp chính

- Thêm kiểm tra file Backup ZIP/JSON và xem số bản ghi trước khi khôi phục.
- Thêm chế độ Gộp/cập nhật bằng upsert.
- Thêm chế độ Thay thế toàn bộ theo thứ tự xóa/nạp phụ thuộc dữ liệu.
- Production yêu cầu tài khoản sở hữu, mật khẩu hiện tại và cụm `KHOI PHUC DU LIEU`.
- Giới hạn file 20 MB, JSON giải nén 100 MB và 100.000 bản ghi.
- Chỉ cho phép các bảng nằm trong danh sách Backup của PES Arena.
- Ghi nhật ký thành công/thất bại của thao tác khôi phục.

## File thay đổi

- `app.py`: phiên bản, đọc/kiểm tra Backup, xem trước, khôi phục Supabase, xóa và upsert theo lô.
- `templates/admin.html`: giao diện kiểm tra và khôi phục.
- `templates/backup_preview.html`: trang xem trước số bản ghi.
- `docs/HUONG_DAN_KHOI_PHUC_SUPABASE_V1.13.4.md`: hướng dẫn vận hành.

---

# V1.13.3 — Tinh gọn Admin và sửa giao diện quản lý trận

- Bỏ giao diện và chặn route của Chuyển giao quyền sở hữu.
- Bỏ giao diện và chặn route của Tạo trận thủ công.
- Bỏ tab Tranh chấp và chặn các route xử lý tranh chấp cũ.
- Đội ngũ quản trị chuyển sang bố cục dạng cột so le, thẻ gọn và không còn khoảng trống lớn.
- Quản lý trận đấu: mỗi trận chỉ còn một hàng; Lưu – Hủy – Xóa nằm cùng hàng; thời gian được định dạng dễ đọc.
- Bổ sung hướng dẫn trực tiếp cho câu xác nhận `SAO LUU DU LIEU`.

## File đã sửa

| File | Nội dung |
|---|---|
| `app.py` | Tăng V1.13.3; bỏ quyền tạo trận/tranh chấp khỏi ma trận; chặn route tính năng đã bỏ |
| `templates/admin.html` | Bỏ 3 phần; bố trí lại bảng trận; thêm hướng dẫn Backup |
| `static/style.css` | Giao diện Admin gọn, dạng cột so le; bảng trận cùng một hàng |

---

# V1.13.2 — Backup dữ liệu, mật khẩu Test và chuyển giao quyền sở hữu

## Thay đổi chính

- Thêm tab **Backup dữ liệu**. Backup tải xuống dạng ZIP, bên trong là JSON của các bảng quan trọng; thao tác chỉ đọc dữ liệu.
- Thêm quyền `backup_manage`; tài khoản sở hữu luôn có quyền, Admin khác phải được cấp riêng.
- Production bắt buộc nhập `SAO LUU DU LIEU` trước khi tạo backup.
- Thêm chế độ mật khẩu đơn giản dành riêng cho môi trường Test bằng `ALLOW_SIMPLE_TEST_PASSWORDS=true`.
- Chỉ khi đồng thời có `APP_ENV=test`, `PES_ARENA_TEST_MODE=true`, `DATABASE_SAFETY_TOKEN=PES_ARENA_TEST_DATABASE` thì mật khẩu một ký tự như `1` mới được chấp nhận.
- Module đổi mật khẩu được đưa vào **Hồ sơ cá nhân → Điều khiển hồ sơ**.
- Đổi mật khẩu chỉ cần mật khẩu hiện tại và mật khẩu mới; bỏ ô nhập lại mật khẩu.
- Thêm chuyển giao quyền sở hữu: chọn người nhận, nhập mật khẩu hiện tại và cụm `CHUYEN GIAO`.
- Sau chuyển giao, chủ cũ trở thành Admin, chủ mới nhận quyền sở hữu và phiên đăng nhập hiện tại bị đóng.
- Sửa `is_owner_user()` để chỉ dựa vào `admin_level=owner`; username `admin` không còn tự động được coi là chủ sau khi đã chuyển giao.
- Cập nhật CSV mẫu lên V1.13.2 và dùng mật khẩu `1` cho môi trường Test.

## File và vị trí đã sửa

| File | Vị trí gần đúng | Nội dung |
|---|---:|---|
| `app.py` | 57 | Tăng phiên bản lên V1.13.2 |
| `app.py` | 167–186 | Cấu hình và kiểm tra mật khẩu đơn giản trong Test Mode |
| `app.py` | 544–567 | Sửa xác định owner; thêm quyền `backup_manage` |
| `app.py` | 3332–3374 | Đơn giản hóa đổi mật khẩu và chuyển về Profile |
| `app.py` | 5862–5927 | Xuất backup ZIP/JSON theo từng bảng |
| `app.py` | 5932–5975 | Chuyển giao quyền sở hữu |
| `app.py` | vùng Import/Reset user | Áp dụng độ dài mật khẩu theo môi trường |
| `templates/profile.html` | 73–91 | Form đổi mật khẩu trong Điều khiển hồ sơ |
| `templates/base.html` | menu trái | Bỏ tab Đổi mật khẩu riêng |
| `templates/admin.html` | 40, 120–132, 562–576 | Tab Backup và form chuyển giao |
| `.env.example` | cuối file | Biến `ALLOW_SIMPLE_TEST_PASSWORDS` |
| `samples/PES_Arena_Import_Tai_Khoan_Mau_v1.13.2.csv` | toàn file | CSV mẫu phiên bản mới |
| `docs/HUONG_DAN_BACKUP_MAT_KHAU_CHUYEN_GIAO_V1.13.2.md` | toàn file | Hướng dẫn sử dụng |

## Cài đặt

1. Backup Production hiện tại trước khi ghi đè code.
2. Chép toàn bộ file của V1.13.2 vào repository.
3. Commit và deploy lên project Test trước.
4. Với project Test, thêm `ALLOW_SIMPLE_TEST_PASSWORDS=true`; không thêm biến này vào Production.
5. Đăng nhập owner, mở **Admin → Backup dữ liệu** để kiểm tra tải ZIP.
6. Mở Profile cá nhân để kiểm tra đổi mật khẩu bằng hai ô.
7. Chỉ thử chuyển giao trên database Test trước.

## Kiểm tra kỹ thuật

- `app.py` biên dịch thành công.
- Toàn bộ template Jinja parse thành công.
- Không có route Flask trùng URL + HTTP method.
- Không có hàm top-level bị khai báo trùng.
- ZIP phát hành không có thư mục cha.

---

# PES Arena – Bản Lĩnh Sân Cỏ

## Phiên bản V1.13.0 – Nâng cấp hệ thống Admin

### Nội dung nâng cấp
- Đổi tên dự án từ PES 2026 thành PES Arena – Bản Lĩnh Sân Cỏ.
- Mở rộng phân quyền Admin theo 6 nhóm: Người dùng, Trận đấu, Vận hành, Hệ thống, RP và Phân quyền.
- Tài khoản sở hữu luôn toàn quyền; mọi tài khoản quản trị chỉ hiển thị chức danh Admin trên giao diện.
- Route backend quan trọng được gắn kiểm tra quyền; Admin không được phép sẽ bị chặn dù nhập URL trực tiếp.
- Thêm công tắc Giao hữu, Chat Sảnh, Chat Phòng, Mã đăng ký và Thông báo; kiểm tra ở giao diện và backend.
- Thêm tab ➕ Tạo trận, tự lưu lịch sử, tính delta1/delta2, RP, thống kê, chuỗi và huy hiệu.
- Cho phép Admin sửa trận trực tiếp tại Profile người chơi.
- Nâng cấp bảng quản lý trận toàn chiều rộng, tiêu đề cố định, cuộn riêng, RP hai người và nút cùng hàng.
- CSV tối đa 500 dòng, UTF-8, 1 MB; hỗ trợ cộng dồn và rank_points âm.
- Thêm công cụ tính lại RP toàn hệ thống từ lịch sử trận hợp lệ.

### File và vị trí đã sửa
- `app.py:`54` – APP_NAME = "PES Arena – Bản Lĩnh Sân Cỏ"
- `app.py:`528` – ADMIN_PERMISSION_GROUPS = {
- `app.py:`574` – def get_system_features():
- `app.py:`3365` – def register():
- `app.py:`4821` – def room_reroll_friendly(room_id):
- `app.py:`4868` – def room_finish_friendly(room_id):
- `app.py:`5737` – def admin_update_system_features():
- `app.py:`5745` – def recalculate_rank_history(from_created_at=None):
- `app.py:`5778` – def admin_create_manual_match():
- `app.py:`6357` – def admin_update_permissions(user_id):
- `app.py:`6710` – def admin_update_match_result(match_id):
- `templates/admin.html:`97` –         <div class="admin-section-heading"><div><h2>🛡️ Đội ngũ quản trị</h2><p class="small">Trên giao diện, mọi tài khoản quản trị đều hiển thị chung là <strong>Admin</strong>.</p></div><span class="admin-count">{{ admins|length }}</span></div>
- `templates/admin.html:`443` –             <table class="admin-match-table">
- `templates/admin.html:`469` – <section class="admin-tab-panel" data-admin-panel="create-match"><div class="panel"><h2>➕ Tạo trận thủ công</h2>
- `templates/admin.html:`533` –     <div class="panel"><h2>🎛️ Bật/tắt tính năng hệ thống</h2><form method="post" action="{{ url_for('admin_update_system_features') }}" class="system-toggle-grid">{% for key,label in {'friendly_enabled':'Giao hữu','lobby_chat_enabled':'Chat Sảnh','room_chat_enabled':'Chat Phòng','registration_codes_enabled':'Mã đăng ký','announcements_enabled':'Thông báo'}.items() %}<label class="admin-permission-option"><span>{{ label }}</span><span class="admin-switch"><input type="checkbox" name="{{ key }}" value="1" {% if system_features.get(key) %}checked{% endif %}><span class="admin-switch-track"></span></span></label>{% endfor %}<button class="btn green" type="submit">Lưu cài đặt</button></form></div>
- `templates/admin.html:`551` – <section class="admin-tab-panel" data-admin-panel="rp-tools"><div class="panel"><h2>📈 Công cụ RP</h2><p>Lịch sử trận là nguồn dữ liệu chuẩn cho RP, thống kê, chuỗi và huy hiệu.</p>{% if can_admin('rp_recalculate_all') %}<form method="post" action="{{ url_for('admin_recalculate_rp') }}" onsubmit="return confirm('Tính lại RP của toàn bộ hệ thống từ lịch sử trận?')"><button class="btn gold" type="submit">Tính lại toàn hệ thống</button></form>{% endif %}</div></section>
- `templates/profile.html:`205` –     <details class="profile-admin-match-edit"><summary>✏️ Admin sửa trận</summary>
- `templates/base.html:`29` –             <div class="brand-wordmark" aria-label="PES Arena">PES Arena <small>– Bản Lĩnh Sân Cỏ</small></div>
- `templates/base.html:`53` –                 {% if active_announcement and system_features.announcements_enabled %}
- `templates/base.html:`162` – {% if system_features.lobby_chat_enabled %}<button id="chatToggleButton" class="chat-floating-toggle" type="button" onclick="toggleLobbyChat()">
- `static/style.css:`3783` – /* PES Arena v1.13.0 - Admin governance */
- `static/style.css:`3785` – .admin-team-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px}
- `static/style.css:`3795` – .admin-match-table{min-width:1320px;width:100%}
- `static/style.css:`3796` – .admin-match-table thead th{position:sticky;top:0;z-index:3;background:var(--panel,#111923)}
- `static/style.css:`3805` – .profile-admin-match-edit{margin-top:10px;padding-top:8px;border-top:1px dashed rgba(255,255,255,.12)}
- `static/style.css:`3806` – .profile-admin-match-edit summary{cursor:pointer;font-weight:700}
- `static/style.css:`3807` – .profile-admin-match-edit form{margin-top:8px;display:flex;align-items:center;gap:6px;flex-wrap:wrap}
- `static/style.css:`3808` – .profile-admin-match-edit input[name="note"]{min-width:220px;flex:1}
- `docs/PES_Arena_v1.13.0_Admin_Upgrade.sql` – Migration Supabase cho quyền JSON, dữ liệu lịch sử RP và công tắc hệ thống.
- `samples/PES_Arena_Import_Tai_Khoan_Mau_v1.13.0.csv` – File CSV mẫu mới.

### Hướng dẫn cài đặt
1. Mở Supabase → SQL Editor.
2. Chạy toàn bộ file `docs/PES_Arena_v1.13.0_Admin_Upgrade.sql`.
3. Giải nén bản V1.13.0 và chép toàn bộ file vào thư mục repository, ghi đè file cũ.
4. Commit và Push lên nhánh thử nghiệm trước.
5. Trong Vercel, Redeploy bản mới và kiểm tra tab Đội ngũ quản trị.
6. Cấp quyền cho từng Admin, kiểm tra bằng tài khoản Admin thường và thử nhập URL trực tiếp.
7. Chỉ chạy “Tính lại toàn hệ thống” sau khi đã sao lưu Supabase.

### Kiểm tra đã thực hiện
- `python -m py_compile app.py`: đạt.
- Kiểm tra cú pháp toàn bộ template Jinja: đạt.
- `python test_rp_engine.py`: đạt, hiển thị OK - RP Engine V1.11.1.
- Không chạy thử kết nối Supabase/Vercel thật vì môi trường đóng gói không có biến môi trường và thư viện Flask/Supabase đầy đủ.

# V1.13.1 — Bản vá an toàn dữ liệu và chống đè lệnh

## File đã sửa

- `app.py`
  - Tách `_safe_int` có dấu và `_safe_bounded_int`, loại bỏ khai báo trùng gây mất RP âm.
  - `ensure_admin()` không còn tự đặt lại mật khẩu owner.
  - Bổ sung quyền `system_features_manage`.
  - Bổ sung kiểm tra backend cho Chat Sảnh và Thông báo.
  - Bổ sung decorator quyền cho xử lý mật khẩu, hủy/xóa phòng và xóa lời mời.
  - Hủy phòng có trận confirmed phải hoàn tác RP trước.
  - Công cụ tính lại RP có khóa chống chạy đồng thời, snapshot và phục hồi khi lỗi.
  - Production bắt buộc nhập `TINH LAI RP` trước khi chạy tính lại toàn hệ thống.
  - Thêm nhận diện Test Mode bằng biến môi trường.
- `templates/admin.html`
  - Thêm cảnh báo Production/Test và ô xác nhận tính lại RP.
- `templates/base.html`
  - Thêm banner vàng khi chạy Test Mode.
- `.env.example`
  - Thêm bộ biến môi trường Test Mode.
- `docs/HUONG_DAN_TEST_AN_TOAN_V1.13.1.md`
  - Hướng dẫn tạo Supabase Test riêng và checklist kiểm thử.

## Lưu ý

Bản vá không biến database Production thành sandbox. Cách test an toàn đúng là dùng một Supabase project Test hoàn toàn riêng.
