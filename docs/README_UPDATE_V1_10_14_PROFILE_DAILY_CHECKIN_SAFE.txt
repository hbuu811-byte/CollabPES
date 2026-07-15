V1.10.14_PROFILE_DAILY_CHECKIN_SAFE

MỤC TIÊU
- Bật điểm danh thật trong Hồ sơ cá nhân -> tab Điểm danh.
- Bật ví ZCOIN thật trong Hồ sơ cá nhân -> tab ZCOIN.
- Daily reward: random 80–150 ZCOIN/ngày.
- Tạm thời chưa phát quà mốc thưởng. Mốc chỉ hiển thị tiến trình để chờ Cửa Hàng/Kho đồ sau này.
- Có hiệu ứng popup + confetti/pháo hoa khi điểm danh thành công.

PHẠM VI CODE
- app.py
- templates/profile.html
- static/style.css
- Log.md
- docs/*

KHÔNG ĐỤNG
- BXH
- phòng đấu
- random đội
- lịch sử trận
- admin hiện tại
- login/register
- logic tính rank

THỨ TỰ TRIỂN KHAI AN TOÀN
1. Backup deployment/source hiện tại.
2. Chạy docs/01_install_v1_10_14_profile_daily_checkin.sql trong Supabase.
3. Chạy docs/02_check_v1_10_14_profile_daily_checkin.sql để kiểm tra.
4. Upload code lên GitHub.
5. Chờ Vercel deploy Ready/Production.
6. Test bằng tài khoản thường: Hồ sơ cá nhân -> Điểm danh.
7. Nếu lỗi giao diện/code: rollback Vercel về deployment trước.
8. Chỉ chạy docs/99_rollback_v1_10_14_profile_daily_checkin.sql nếu muốn xóa hẳn dữ liệu ZCOIN/điểm danh mới.
