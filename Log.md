# Collap_V1.13.3j — Thu gọn Lịch sử đấu trong phòng thành bảng tỷ số

- **Ngày giờ:** 18/07/2026 23:18 — Asia/Bangkok
- **Phiên bản nền:** Collap_V1.13.3i
- **Phiên bản đối chiếu giao diện phòng:** Collap_V1.13.3e và Collap_V1.13.3f
- **Phạm vi:** Chỉ thay đổi giao diện Lịch sử đấu trong phòng; không sửa dữ liệu trận, RP, polling hoặc Supabase.

## Nội dung đã sửa

1. Bỏ thời gian của từng trận khỏi Lịch sử đấu trong phòng.
2. Bỏ hoàn toàn số `+/- RP` của từng trận.
3. Bỏ bảng tổng hợp thắng–hòa–thua và mốc thời gian mở phòng khỏi khối này.
4. Chỉ giữ tên hai người chơi và các tỷ số trong phiên phòng.
5. Trình bày tỷ số thành bảng 3 cột rõ ràng:
   - Điểm của Chủ phòng.
   - Dấu phân cách.
   - Điểm của Khách.
6. Điểm của người thắng trong từng dòng được nhấn màu vàng để dễ quan sát.
7. Giữ danh sách cuộn gọn, tối đa theo dữ liệu 8 trận mới nhất mà backend hiện có.
8. Bổ sung giao diện tương thích Dark Mode, Light Mode và màn hình nhỏ.

## File đã sửa

| File | Khoảng dòng ước lượng | Nội dung |
|---|---:|---|
| `app.py` | khoảng dòng 65 | Tăng phiên bản từ `Collap_V1.13.3i` lên `Collap_V1.13.3j`. |
| `templates/room_detail.html` | khoảng dòng 310–342 | Thay khối lịch sử cũ bằng bảng chỉ hiển thị tỷ số. |
| `static/style.css` | khoảng dòng 4347–4456 | Giao diện bảng tỷ số mới trong cột phải của phòng đấu. |

## Không thay đổi

- Không sửa công thức RP.
- Không sửa cách lưu lịch sử trận trong Supabase.
- Không sửa cơ chế bỏ cuộc.
- Không sửa trạng thái phòng.
- Không sửa polling hoặc API trạng thái phòng.
- Không cần chạy SQL Supabase.

## Cách cài đặt

Chép đè ba file sau lên dự án đang chạy `Collap_V1.13.3i`:

```text
app.py
templates/room_detail.html
static/style.css
```

Sau đó Commit, Push và triển khai lên nhánh test trước.
