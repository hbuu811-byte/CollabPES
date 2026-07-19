# PES Arena V1.13.5 – Bộ Công Cụ Tính RP

## Ba chức năng

1. **Backup RP**: tải ZIP chỉ chứa trạng thái RP/thống kê của người chơi và delta RP đã lưu trên từng trận.
2. **Restore RP**: ghi đè lại đúng các trường RP/thống kê từ file backup; không sửa tỷ số, không xóa tài khoản và không tạo/xóa trận.
3. **Tính lại RP**: dựng lại RP từ lịch sử các trận `confirmed` theo thứ tự thời gian.

## Câu xác nhận Production

- Backup: `SAO LUU RP`
- Restore: `KHOI PHUC RP` và mật khẩu hiện tại của tài khoản sở hữu
- Tính lại: `TINH LAI RP`

## Dữ liệu nằm trong RP Backup

### Người chơi

`id`, `rank_points`, `wins`, `draws`, `losses`, `total_matches`, `goals_for`, `goals_against`, `streak`, `loss_streak`.

### Trận đấu

`id`, `delta1`, `delta2`, `rp_formula_version`, `rp_details`.

Backup không chứa password, chat, phòng, lời mời, mã đăng ký hoặc cấu hình hệ thống.

## Cơ chế tính lại RP

1. Khóa công cụ để không có hai tiến trình chạy đồng thời.
2. Chụp snapshot người chơi và các trận hợp lệ để phục hồi khi có lỗi.
3. Lấy duy nhất trận có `status = confirmed` và sắp xếp `created_at` từ cũ đến mới.
4. Đặt người chơi về 1.000 RP; thống kê và chuỗi về 0.
5. Đưa toàn bộ trận hợp lệ về `waiting_confirm` trước khi tính trận đầu tiên. Điều này ngăn trận tương lai làm sai chuỗi thắng/thua của trận đang tính.
6. Xử lý từng trận theo thời gian. ID trận tạo hạt ngẫu nhiên cố định, vì vậy cùng lịch sử và cùng công thức sẽ cho cùng kết quả khi chạy lại.
7. Cập nhật RP, thắng/hòa/thua, bàn thắng/bàn thua, chuỗi, delta1 và delta2.
8. Nếu một bước lỗi, hệ thống cố gắng phục hồi snapshot.

## Công thức đang chạy

- Thắng cơ bản: ngẫu nhiên 21–23 RP.
- Biến thiên thắng: ngẫu nhiên -1 đến +3 RP.
- Trong 10 trận đầu: cộng ngẫu nhiên +1 đến +4; tổng RP thắng bị giới hạn 22–29.
- Thưởng chuỗi thắng: trận chạm mốc 3 cộng 5; mốc 5 cộng 10; mốc 10 và mỗi 5 trận tiếp theo cộng 15.
- Thua trong 10 trận đầu: trừ 14–19 RP.
- Sau 10 trận: trừ 19–23 RP.
- Chuỗi thua từ trận thua thứ 4 làm mức trừ tăng dần; từ 7 trở lên trừ 25–30 RP.
- Chủ phòng thắng: RP dương nhân 0,95; trong 10 trận đầu vẫn giữ giới hạn 22–29.
- Hòa: người Rank thấp hơn được +5, người còn lại +0; cùng Rank +0/+0.
- RP người chơi không xuống dưới 0.

## Quy trình an toàn

1. Dừng xác nhận trận mới.
2. Bấm Backup RP và giữ file ZIP.
3. Chạy Tính lại RP.
4. Kiểm tra bảng xếp hạng và một số Profile.
5. Nếu kết quả không đúng, dùng Restore RP với file vừa tải.
