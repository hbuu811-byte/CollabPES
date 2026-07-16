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
