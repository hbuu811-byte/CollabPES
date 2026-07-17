# PES Arena V1.13.13-v4.1 FIX1

- `templates/room_detail.html`: thêm nút **Thoát Phòng** bên cạnh **Mời Đấu** khi chủ phòng đang chờ đối thủ.
- `apply_players_action_column.py`: đưa cột **HÀNH ĐỘNG** trong bảng Cộng đồng Player sang cột thứ 2, ngay sau PLAYER.
- Không sửa `app.py`, database, công thức RP hoặc polling.

## Cách dùng
1. Chép `templates/room_detail.html` đè vào dự án.
2. Chép `apply_players_action_column.py` vào thư mục gốc, cùng cấp `app.py`.
3. Chạy: `python apply_players_action_column.py`.
4. Có thể xóa script sau khi chạy thành công.
