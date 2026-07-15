# Rank PES Collaboration V1.10.47

Bản tối ưu an toàn trên nền V1.10.46.

## Điểm chính
- Sửa lỗi trang Admin do biến Realtime bị thiếu trong Jinja context.
- Cache BXH công khai và Realtime/polling fallback được giữ nguyên.
- Giảm dữ liệu đọc từ Supabase bằng danh sách cột rõ ràng.
- Lịch sử hồ sơ phân trang 20 trận/trang và không tải toàn bộ bảng matches.
- Không cần chạy SQL.

## Biến môi trường
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_ANON_KEY`
- `SUPABASE_REALTIME_ENABLED=1`
- `SUPABASE_MAX_CONCURRENT=2`
- `FLASK_SECRET_KEY`
- `APP_ENV=production`
