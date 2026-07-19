# Collap_V1.13.3m — Lịch sử toàn hệ thống và bộ lọc bỏ cuộc

- Ngày giờ: 19/07/2026 — múi giờ Asia/Bangkok.
- Bản nền chức năng: `Collap_V1.13.3k`.
- Không gộp các nhánh `l/lv2/lv3` đang thử nghiệm Request.
- Loại gói: trình vá tự động, chỉ sửa đúng các file liên quan trên nhánh được chọn.
- SQL Supabase: không cần.

## 1. Lịch sử trận — Toàn hệ thống

- Thêm công tắc hệ thống `match_history_all_enabled`, mặc định bật.
- Admin có quyền `system_features_manage` được bật/tắt tại:
  - Admin → Bật/tắt tính năng hệ thống → `Xem lịch sử toàn hệ thống`.
- Khi bật:
  - Người chơi thấy tab `Toàn hệ thống` như hiện tại.
- Khi tắt:
  - Người chơi chỉ thấy `Trận của tôi`.
  - Cố mở trực tiếp `/matches?view=all` cũng bị backend chuyển về dữ liệu của chính tài khoản.
  - Admin vẫn xem được toàn hệ thống để quản lý và kiểm tra dữ liệu.

## 2. Bộ lọc Đã hủy / Bỏ cuộc

Bộ lọc `status=cancelled` được mở rộng để nhận:

- Mọi dòng có `status = cancelled`.
- Dòng có marker hoặc ghi chú bỏ cuộc.
- Dòng bị trừ RP (`delta1 < 0` hoặc `delta2 < 0`) nhưng không phải trận confirmed thua bình thường.
- Không yêu cầu phải có đủ cả `player1_id` và `player2_id`.

Nhờ vậy các lần hệ thống đã trừ điểm vẫn xuất hiện trong `Toàn hệ thống`, kể cả bản ghi chỉ có một người chơi hoặc phòng chưa gắn đủ đối thủ.

## 3. File được trình vá sửa

| File | Nội dung |
|---|---|
| `app.py` | Đổi version; thêm mặc định `match_history_all_enabled = True` |
| `modules/match_history_routes.py` | Khóa xem toàn hệ thống ở backend; mở rộng bộ lọc hủy/bỏ cuộc; giữ góc nhìn cá nhân/toàn hệ thống |
| `templates/matches.html` | Ẩn tab Toàn hệ thống khi bị tắt; đổi tên bộ lọc thành `Đã hủy / Bỏ cuộc` |
| `templates/admin.html` | Thêm công tắc `Xem lịch sử toàn hệ thống` |

## 4. An toàn khi áp dụng

- Trình vá tạo backup tại `.collap_v1_13_3m_backup` trước khi ghi file.
- Nếu Python compile thất bại, trình vá tự khôi phục file cũ.
- Không sửa công thức RP.
- Không sửa cơ chế bỏ cuộc/phạt điểm.
- Không sửa polling, chat, trạng thái phòng hoặc file JavaScript.
- Không cập nhật `created_at` và không sửa schema Supabase.

## 5. Cách áp dụng

1. Chọn đúng nhánh cần thử, dựa trên `Collap_V1.13.3k` hoặc nhánh Request đã gộp đủ chức năng đến 3k.
2. Chép `apply_Collap_V1.13.3m.py` vào thư mục gốc, cùng cấp `app.py`.
3. Chạy:

```bash
python apply_Collap_V1.13.3m.py
```

4. Commit bốn file được báo đã sửa.
5. Không commit thư mục `.collap_v1_13_3m_backup`.
6. Deploy nhánh test và kiểm tra:
   - bật công tắc → người chơi thấy Toàn hệ thống;
   - tắt công tắc → người chơi chỉ thấy Trận của tôi;
   - Admin vẫn xem được Toàn hệ thống;
   - lọc Đã hủy / Bỏ cuộc nhận các dòng delta âm và bản ghi thiếu một phía.
