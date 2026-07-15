# PES 2026 WEB — V1.10.66 Hybrid UI

## Nền tảng
- Nâng cấp trực tiếp từ V1.10.65 Hybrid.
- Giữ luồng backend và cơ chế thao tác phòng đấu của V1.10.15 để ưu tiên tốc độ phản hồi.
- Giữ các tính năng nâng cấp đã ghép từ V1.10.64c: ZCOIN, điểm danh, cửa hàng, kho vật phẩm, Gift Code, Achievement, hồ sơ và Admin mở rộng.

## Nâng cấp V1.10.66
- Thay `static/style.css` bằng bộ giao diện đầy đủ của V1.10.64c.
- Khôi phục giao diện eSports, khung Rank, Avatar, Achievement, bảng xếp hạng, hồ sơ, cửa hàng, kho đồ và giao diện Admin của V1.10.64c.
- Bổ sung manifest 5 banner hồ sơ tại `docs/assets-manifests/` để đối chiếu tên file, độ hiếm và giá ZCOIN.
- Không đưa cơ chế room fragment, HTMX room refresh hoặc polling dày của V1.10.64c trở lại backend.

## Cách cài đặt
1. Giải nén V1.10.66 vào thư mục dự án.
2. Copy toàn bộ thư mục `static` của bản V1.10.64c vào thư mục gốc V1.10.66.
3. Chọn gộp thư mục và ghi đè file khi Windows hỏi.
4. Đảm bảo file cuối cùng `static/style.css` là file đi kèm V1.10.66 hoặc đúng file `style.css` V1.10.64c đã cung cấp.
5. Commit lên một nhánh test trước khi merge vào `main`.

## Lưu ý tài nguyên ảnh
- Gói này vẫn có tài nguyên nền từ V1.10.65 để có thể mở dự án ngay.
- Bộ ảnh hoàn chỉnh của V1.10.64c cần được copy vào `static` để khung Rank, banner, shop và các hình ảnh mới hiển thị đầy đủ.
- Các bản nâng cấp sau V1.10.66 có thể chỉ phát hành file code/CSS/template thay đổi, không cần đóng gói lại toàn bộ ảnh.

## Kiểm tra bắt buộc trước khi đưa lên main
- Đăng nhập bằng hai tài khoản trên hai trình duyệt.
- Kiểm tra Quay quân, nhập tỷ số, Xác nhận và Đá tiếp.
- Kiểm tra khung Rank, Avatar, logo CLB và ảnh banner.
- Kiểm tra F12 Console không có lỗi JavaScript.
- Kiểm tra Network không xuất hiện polling dày hoặc request `state-fragment` liên tục.
