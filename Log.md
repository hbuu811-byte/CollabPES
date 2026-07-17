# PES Arena V1.13.13-v4.1

## Nền phát triển
- Kế thừa bản V1.13.13-v3 đã sửa lag, nháy và reset kết quả.

## Thay đổi
- Polling trạng thái phòng theo từng trạng thái thay vì một chu kỳ cố định.
- Khi đang thi đấu: máy chủ kiểm tra mỗi khoảng 8 giây; máy khách khoảng 3 giây để nhận kết quả nhanh hơn.
- Khi chờ xác nhận kết quả: kiểm tra mỗi khoảng 1 giây.
- Khi chờ sẵn sàng: khoảng 2,5 giây.
- Khi tab bị ẩn: giảm còn khoảng 15 giây.
- Kiểm tra ngay khi quay lại tab hoặc cửa sổ được focus.
- Chặn request State chạy chồng lên nhau.
- Hủy request và timer khi rời trang.
- Gửi state_key hiện tại lên server; nếu phòng chưa thay đổi, API trả 204 rỗng để giảm dữ liệu truyền.
- Giữ nguyên cơ chế bảo vệ tỷ số đang nhập của V3.

## File cần cập nhật
- app.py
- templates/room_detail.html
