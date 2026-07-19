# Kiến trúc module – Collap_V1.13.2

## Mục tiêu

- Mỗi nhóm nâng cấp có một file riêng, tránh sửa đồng thời nhiều vùng trong `app.py`.
- Giữ nguyên toàn bộ URL/endpoint Flask cũ để template, JavaScript và link đang dùng không bị hỏng.
- Công thức RP chỉ nằm trong `modules/rp_formula.py` và `modules/rp_engine.py`.
- Luồng áp dụng, hoàn tác và phát lại RP dùng chung một nguồn dịch vụ; không viết lại công thức trong route Admin hoặc route phòng.

## Sơ đồ file cần sửa theo chức năng

| Chức năng cần nâng cấp | File chính |
|---|---|
| Vào phòng, link chia sẻ, xem phòng, rời phòng | `modules/room_access_routes.py` |
| Bỏ cuộc, đá lại | `modules/room_rematch_routes.py` |
| Quay đội, giao hữu, sẵn sàng | `modules/room_team_routes.py` |
| Nhập/xác nhận/tranh chấp kết quả | `modules/room_result_routes.py` |
| Trang lịch sử trận | `modules/match_history_routes.py` |
| Khóa khi Admin đang phát lại BXH | `modules/ranking_lock_service.py` |
| Cộng/trừ RP, cập nhật W-D-L, streak, hoàn tác trận | `modules/match_result_service.py` |
| Phát lại toàn bộ lịch sử sau khi sửa trận | `modules/ranking_rebuild_service.py` |
| Xóa phòng/trận/tài khoản an toàn | `modules/data_cleanup_service.py` |
| Công thức và các mốc RP | `modules/rp_formula.py` |
| Bộ máy tính RP | `modules/rp_engine.py` |
| Helper sửa tỷ số Admin | `modules/admin_match_service.py` |
| Dựng kế hoạch phát lại lịch sử | `modules/admin_ranking_rebuild.py` |
| Admin bảo trì, công tắc hệ thống, backup RP, chuyển owner | `modules/admin_system_routes.py` |
| Trang tổng quan Admin | `modules/admin_dashboard_routes.py` |
| Tài khoản, CSV, duyệt/khóa và phân quyền Admin | `modules/admin_account_routes.py` |
| Sửa tỷ số/trạng thái và tranh chấp | `modules/admin_match_routes.py` |
| Sửa/reset/xóa người chơi | `modules/admin_player_routes.py` |
| Xóa trận, phòng và lời mời | `modules/admin_data_routes.py` |
| Đăng nhập, profile, dashboard, BXH và helper dùng chung | `app.py` |

## Quy tắc sửa để không chồng chéo

1. Không chép công thức RP vào route hoặc template.
2. Route chỉ đọc form, kiểm tra quyền và gọi service.
3. Mọi thao tác sửa trận đã confirmed phải dùng khóa trong `ranking_lock_service.py`.
4. Sửa tỷ số/trạng thái phải gọi `rebuild_rankings_after_admin_change()`; không cộng/trừ RP thủ công.
5. Không cập nhật `created_at` khi Admin sửa trận.
6. Không tạo thêm route cùng URL và HTTP method.
7. Khi thêm module route mới, đăng ký tại khối **Đăng ký module chức năng** cuối `app.py`.
8. Mỗi lần phát hành phải tăng phiên bản tuần tự và cập nhật `Log.md`.

## Thứ tự dependency lúc khởi động

```text
ranking_lock_service
    ↓
match_result_service
    ↓
ranking_rebuild_service
    ↓
data_cleanup_service
    ↓
room_*_routes / admin_*_routes
```

Thứ tự này bảo đảm route phòng và Admin đều dùng cùng một logic RP và hoàn tác dữ liệu.
