# PES Arena V1.13.9 – Tinh gọn quản lý trận và RP

## Đã loại bỏ hoàn toàn

- Route Admin sửa tỷ số trận đấu.
- Biểu mẫu sửa tỷ số trong trang Admin.
- Biểu mẫu sửa tỷ số trong Profile người chơi.
- Hàm tính lại/Reset RP toàn hệ thống từ lịch sử trận.
- Route và nút `TINH LAI RP`.
- Quyền `matches_edit`, `rp_edit_match`, `rp_recalculate_all`.
- Route tạo trận thủ công cũ đã bị vô hiệu hóa nhưng vẫn còn thân hàm.
- Route sửa tỷ số tranh chấp cũ đã bị vô hiệu hóa nhưng vẫn còn thân hàm.

## Vẫn giữ

- Xem tỷ số, RP và trạng thái trận.
- Hủy trận và hoàn tác đúng RP của trận đó.
- Xóa trận và hoàn tác đúng RP của trận đó.
- Backup RP toàn hệ thống.
- Restore RP từ file Backup.
- Công thức RP trong `modules/rp_formula.py`.
- Bộ máy tính RP cho các trận mới trong `modules/rp_engine.py`.

## Cài đặt

1. Sao lưu repository hiện tại.
2. Giải nén ZIP và chép đè toàn bộ file vào repository.
3. Commit và Push.
4. Redeploy Vercel.
5. Không cần chạy SQL trên Supabase.

## Kiểm tra sau khi cài

- Admin → Trận đấu chỉ còn xem tỷ số, Hủy và Xóa.
- Profile không còn mục “Admin sửa trận”.
- Bộ Công Cụ RP chỉ còn Backup RP và Restore RP.
- URL cũ `/admin/rp/recalculate` và `/admin/match/<id>/update-result` trả về 404.
