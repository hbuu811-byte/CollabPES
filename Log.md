# Collap_V1.13.3e — Chuyển lịch sử đấu sang cột phải và giảm trễ phía khách

- **Ngày giờ:** 18/07/2026 18:03 — Asia/Bangkok
- **Bản nền:** Collap_V1.13.3d
- **Loại gói:** Chỉ chứa các file cần chép đè
- **SQL Supabase:** Không cần

## Nội dung thay đổi

### 1. Chuyển LỊCH SỬ ĐẤU xuống dưới Thông tin phòng đấu
- Di chuyển toàn bộ khối lịch sử phiên khỏi phần `Điều khiển phòng`.
- Đặt lịch sử ở cột phải, ngay dưới `Thông tin phòng đấu`, đúng vùng trống trên ảnh yêu cầu.
- Thu gọn bố cục để phù hợp cột nhỏ: tổng trận, W-D-L, tỷ số, thời gian và RP.
- Hiển thị tối đa 8 trận mới nhất trong danh sách cuộn; tổng W-D-L vẫn tính trên toàn bộ trận của phiên phòng.
- Trên màn hình hẹp, cột phải tự chuyển thành bố cục responsive, không làm vỡ hai thẻ CLB.

### 2. Giảm độ trễ khi phía khách nhận thay đổi
- Trước đây mỗi lần phía khách phát hiện trạng thái đổi và tải lại trang, lịch sử phòng gọi `list_matches("confirmed")`, kéo/làm giàu toàn bộ lịch sử trận hệ thống.
- Thay bằng truy vấn nhỏ chỉ đọc đúng hai người chơi, trạng thái `confirmed`, kể từ thời điểm mở phòng và chỉ chọn các cột cần thiết.
- Có fallback về cơ chế cũ nếu truy vấn lọc cặp tạm thời lỗi, để lịch sử phụ không làm hỏng phòng đấu.
- Giảm nhịp chờ đồng bộ của khách khi đang `playing` từ 3.000 ms xuống 2.200 ms. API không đổi vẫn trả HTTP 204 khi trạng thái chưa đổi, nên payload lặp rất nhỏ.
- Khi Chat phòng bị tắt, trình duyệt không còn chạy poll chat ngầm.
- Khi Chat phòng bật nhưng nội dung chưa đổi, không dựng lại toàn bộ DOM tin nhắn.

## File đã sửa và vị trí ước lượng

| File | Khoảng dòng | Nội dung |
|---|---:|---|
| `app.py` | 65 | Nâng phiên bản lên `Collap_V1.13.3e` |
| `app.py` | 3046–3150 | Tối ưu `build_room_head_to_head()` bằng truy vấn cặp trực tiếp, fallback an toàn và giới hạn 8 dòng hiển thị |
| `templates/room_detail.html` | 294–358 | Đưa LỊCH SỬ ĐẤU vào cột phải, dưới Thông tin phòng đấu |
| `templates/room_detail.html` | 646–660 | Điều chỉnh nhịp đồng bộ phía khách khi đang thi đấu |
| `templates/room_detail.html` | 756–826 | Chỉ chạy chat poll khi bật và tránh render lại khi dữ liệu không đổi |
| `static/style.css` | cuối file | Giao diện lịch sử dạng sidebar và responsive |

## Những phần không thay đổi

- Không sửa công thức RP.
- Không sửa xác nhận, hủy, bỏ cuộc hoặc trừ 20 RP.
- Không sửa dữ liệu trận trong Supabase.
- Không thay đổi `created_at` của trận hoặc phòng.
- Không thêm bảng, cột, trigger hay SQL.
- Giữ nguyên các modal thoát phòng của Collap_V1.13.3d.

## Kiểm tra

- Biên dịch Python `app.py` và toàn bộ `modules/*.py`.
- Import Flask app trong thư mục sạch.
- So sánh route với Collap_V1.13.3d, không được mất hoặc trùng route.
- Parse toàn bộ template Jinja.
- Mô phỏng truy vấn lịch sử đúng cặp host/guest và kiểm tra đảo tỷ số/RP khi host là player2.
- Kiểm tra ZIP không bọc thư mục cha, không chứa `.pyc`, `__pycache__` hoặc file backup.
