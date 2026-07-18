# Log — PES Arena V1.13.13-v4.9.1

- **Ngày giờ:** 18/07/2026, múi giờ Asia/Bangkok
- **Gói sửa:** `PES_Arena_V1.13.13-v4.9.1_Admin_Doi_Trang_Thai_Tinh_Lai_Lich_Su.zip`
- **Cơ sở ghép mã:** Giữ giao diện phân quyền trực tiếp từ file người dùng gửi; backend lấy từ nhánh gần nhất đã có trên hệ thống, sau đó sửa tiếp. Không dựng lại dự án từ đầu.

## Nội dung đã sửa

1. **Admin thay đổi tỷ số và trạng thái trận**
   - Cho phép chuyển giữa: `playing`, `waiting_confirm`, `disputed`, `confirmed`, `cancelled`.
   - Quyền `matches_confirm` mới được sửa tỷ số/xác nhận.
   - Quyền `matches_cancel` mới được chuyển sang trạng thái hủy.
   - Admin phụ dùng chung đúng logic với Admin chính theo quyền đã được cấp.

2. **Giữ nguyên mốc thời gian lịch sử**
   - Mọi lần sửa chỉ cập nhật `updated_at`.
   - Không đưa `created_at` vào payload cập nhật hoặc rollback.
   - Trận cũ được phát lại đúng vị trí theo `created_at`, sau đó dùng `id` để ổn định thứ tự nếu trùng thời gian.

3. **Tính lại toàn bộ dữ liệu phụ thuộc lịch sử**
   - RP của cả hai người chơi.
   - Tổng trận, thắng, hòa, thua.
   - Bàn thắng, bàn thua.
   - `streak` và `loss_streak`.
   - `winner_id`, `loser_id`, `delta1`, `delta2`, phiên bản/cấu trúc chi tiết công thức RP.
   - Tính lại cả các trận nằm sau trận bị sửa vì Rank, số trận đầu và chuỗi thắng/thua có thể làm thay đổi RP.

4. **Không làm mất dữ liệu gốc/import/legacy**
   - Mốc gốc được tính bằng dữ liệu hiện tại trừ phần đã sinh ra từ các trận confirmed đang lưu.
   - Không còn đặt toàn bộ W-D-L và tổng trận về 0 trước khi phát lại.
   - Giữ đúng số trận gốc để công thức 10 trận đầu không bị kích hoạt lại sai.
   - Trận legacy còn tham chiếu tài khoản đã xóa vẫn được phát lại bằng delta đã lưu cho người chơi còn tồn tại, thay vì làm lỗi toàn bộ BXH.

5. **Khóa luồng chống cộng/trừ RP chồng chéo**
   - Thêm khóa toàn cục trong bảng `system_settings`, có hiệu lực giữa nhiều Vercel Serverless Function/instance.
   - Khóa có token và tự hết hạn sau 5 phút để tránh kẹt vĩnh viễn.
   - Nút xác nhận của người chơi kiểm tra khóa trước và sau khi claim `processing_result`.
   - Admin không phát lại lịch sử khi còn trận đang ở `processing_result`.
   - Kiểm tra lại trạng thái/tỷ số/`updated_at` sau khi giành khóa để không ghi đè thay đổi vừa xảy ra.

6. **Đồng bộ phòng đấu đúng cấu trúc**
   - Dùng `host_score` và `guest_score` thay vì ghi nhầm `score1`/`score2` vào `match_rooms`.
   - Ánh xạ `waiting_confirm` của trận thành `waiting_result_confirm` của phòng.
   - Đồng bộ `confirmed_by_id`, `state_expires_at`, trạng thái và ghi chú.

7. **Các luồng liên quan**
   - Xác nhận tranh chấp cũ được phát lại theo thời gian trận gốc.
   - Hủy trận confirmed tính lại lịch sử thay vì chỉ trừ delta trực tiếp.
   - Xóa trận confirmed phát lại lịch sử trước khi xóa.
   - Khi cập nhật giữa chừng thất bại, hệ thống rollback best-effort dữ liệu người chơi và trận đã ghi.

## File đã chỉnh sửa

### `app.py`
- Khoảng dòng **109–115**: khai báo khóa phát lại BXH.
- Khoảng dòng **5516–5595**: khóa luồng nhập kết quả và kiểm tra cập nhật có thực sự thành công.
- Khoảng dòng **5657–5735**: khóa luồng tạo tranh chấp khi Admin đang tính lại lịch sử.
- Khoảng dòng **5883–6090**: quản lý khóa DB, kiểm tra stale lock, đồng bộ phòng và kiểm tra dữ liệu cạnh tranh.
- Khoảng dòng **6091–6224**: bổ sung khóa hai lớp cho luồng xác nhận kết quả.
- Khoảng dòng **6226–6294**: xác nhận tranh chấp bằng phát lại lịch sử theo thời gian gốc.
- Khoảng dòng **6419–6565**: lập kế hoạch, cập nhật, rollback và xóa cache sau khi tính lại BXH.
- Khoảng dòng **7669–7790**: Admin sửa tỷ số/trạng thái, kiểm tra quyền và chống ghi đè luồng khác.
- Khoảng dòng **7790–7888**: hủy/xác nhận tranh chấp theo logic phát lại.
- Khoảng dòng **8040–8095**: xóa trận sau khi hoàn tác bằng phát lại lịch sử.

### `modules/admin_ranking_rebuild.py`
- Khoảng dòng **1–183**: tính mốc gốc RP, W-D-L, bàn thắng/thua và suy ra streak gốc.
- Khoảng dòng **184–326**: phát lại theo `created_at`, tính delta RP, host factor, placement, winner/loser và xử lý lịch sử orphan/legacy.

### `templates/admin.html`
- Khoảng dòng **3–10**: kiểu hiển thị ô sửa tỷ số/trạng thái.
- Khoảng dòng **366–420**: giao diện sửa tỷ số, trạng thái, ghi chú; ẩn/khóa thao tác theo quyền Admin.

## Kiểm tra đã thực hiện

- `python -m py_compile app.py`: đạt.
- `python -m py_compile modules/admin_ranking_rebuild.py`: đạt.
- Jinja parse `templates/admin.html`: đạt.
- Test giữ nguyên dữ liệu legacy khi phát lại lịch sử không thay đổi: đạt.
- Test đảo người thắng và tính lại RP/W-D-L/streak/loss_streak: đạt.
- Test confirmed → cancelled, xóa delta và winner/loser: đạt.
- Test trận tham chiếu người chơi đã xóa không làm hỏng toàn bộ BXH: đạt.
- Kiểm tra mọi lời gọi phát lại đều truyền khóa sở hữu: đạt.

## Lưu ý triển khai

- Gói này là **bản vá gồm đúng các file cần thay**, không phải bản full.
- Sao chép ba file mã nguồn vào đúng vị trí trong dự án full rồi deploy lại.
- Bảng `system_settings` đang được dự án sử dụng và cần có khóa duy nhất theo `setting_key` như cấu trúc hiện tại.
