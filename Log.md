# Collap_V1.13.3lv3.6 — Khôi phục đúng bố cục phòng đấu

- Ngày giờ: 20/07/2026, múi giờ Asia/Bangkok.
- Bản nền hỗ trợ: `Collap_V1.13.3lv3.4` hoặc `Collap_V1.13.3lv3.5`.
- Phạm vi: chỉ sửa cơ chế cập nhật giao diện phòng.
- SQL Supabase: không cần.

## Nguyên nhân xác nhận lại

Hai bản `lv3.4` và `lv3.5` đều can thiệp vào cấu trúc DOM bên trong grid phòng:

- `lv3.4` morph node đệ quy theo vị trí/key.
- `lv3.5` thay từng thẻ Chủ, VS, Khách và thanh bên bằng selector.

Giao diện thực tế của dự án có nhiều nhánh trạng thái và wrapper khác nhau. Chỉ cần một
selector hoặc vị trí node không khớp là thẻ Chủ, VS hoặc Khách bị đưa sai khỏi grid,
làm khung Rank/CLB kéo rộng gần toàn màn hình.

## Cách sửa lv3.6

- Xóa hoàn toàn hai thuật toán morph/replace theo node.
- Khi trạng thái thật sự thay đổi, server vẫn chỉ trả `_room_live_content.html`.
- Client thay nguyên nội dung bên trong `#roomLiveContent` bằng fragment chuẩn từ server.
- Không reload `Document`, `base.html`, menu, CSS hoặc JavaScript.
- Chỉ thực hiện thay fragment khi HTML mới khác cache.
- Kiểm tra fragment phải có đủ cấu trúc phòng trước khi đưa vào trang.
- Giữ tỷ số đang nhập, checkbox/select, focus, vị trí con trỏ, nội dung chat đang gõ,
  vị trí cuộn chat và vị trí cuộn trang.
- Ảnh Rank/CLB/giao diện tiếp tục dùng cache trình duyệt hiện có.
- Đổi cache sang `pes-room-fragment-cache-v3:<room_id>` và xóa hai cache lỗi cũ.

## File được sửa sau khi chạy

| File | Nội dung |
|---|---|
| `app.py` | Tăng phiên bản thành `Collap_V1.13.3lv3.6` |
| `templates/room_detail.html` | Thay bộ vá DOM bằng thay fragment phòng an toàn |

## Không thay đổi

- Không sửa CSS hoặc kích thước khung Rank/CLB.
- Không sửa RP, lịch sử trận, bỏ cuộc, Admin hoặc Supabase.
- Không thay đổi API chat, khóa request hay watchdog của nhánh `lv3.4`.
- Không đưa lại reload toàn bộ trang.

## Cài đặt

1. Chép ba file trong gói vào thư mục gốc dự án, cùng cấp với `app.py`.
2. Chạy `APPLY_Collap_V1.13.3lv3.6.bat`.
3. Commit đúng `app.py` và `templates/room_detail.html`.
4. Không commit `.collap_v1_13_3lv3_6_backup`.
5. Push và redeploy Vercel.
6. Sau deploy, tải lại trang phòng một lần để nhận JavaScript mới.

## Kịch bản kiểm tra

1. Tạo phòng chưa có khách: Chủ – VS – Khách nằm cùng một hàng như giao diện gốc.
2. Khách tham gia: chỉ phần phòng đổi, không tải lại trang.
3. Sẵn sàng, quay đội, gửi kết quả: bố cục không bị kéo rộng.
4. Đang nhập tỷ số khi đối thủ thao tác: tỷ số không bị xóa.
5. Chat đang gõ hoặc đang cuộn: nội dung và vị trí được giữ.
