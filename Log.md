# V1.10.64 — Tối ưu phản hồi Quay quân, Xác nhận và Đá tiếp

## Mục tiêu

Giảm thời gian chờ trực tiếp giữa hai màn hình người chơi tại ba thao tác quan trọng trong phòng đấu.

## Thay đổi

- Thêm `get_room_action_state()` chỉ lấy các cột cần thiết cho POST thao tác, không chạy `enrich_room()` và không tải toàn bộ danh sách người chơi.
- `Quay quân`, `Xác nhận kết quả`, `Đá tiếp` dùng room state tối giản.
- Lấy thông tin hai người chơi bằng một request `get_users_by_ids()` thay vì hai request tuần tự.
- `enrich_room()` chỉ tải đúng chủ phòng và khách, không dùng `users_map()` để tải/sắp xếp toàn bộ BXH.
- POST thành công trả `204` ngay; trình duyệt tải fragment mới bằng request riêng sau đó.
- Đồng bộ Achievement được đẩy ra khỏi request Xác nhận bằng tác vụ hậu kỳ best-effort.
- `apply_match_result()` nhận trực tiếp `host_user_id`, bỏ một truy vấn tìm chủ phòng trong luồng xác nhận.
- Kiểm tra xung đột Đá tiếp được gộp thành hai query Supabase đã lọc trực tiếp.
- Không thay đổi database, không cần chạy SQL.

## Kết quả dự kiến

- Quay quân: giảm tải room/user trước thao tác và không render fragment trong POST.
- Xác nhận: giảm một request user, một request host và loại bỏ quét Achievement khỏi đường chờ chính.
- Đá tiếp: giảm từ bốn lần kiểm tra riêng xuống hai query đã lọc.
- Màn hình đối thủ vẫn nhận cập nhật qua Supabase Realtime; polling tiếp tục làm lớp dự phòng.

---

# V1.10.63 — Tối ưu phòng đấu giai đoạn 1 và backend nhẹ

- Tạo `get_room_state_light()` cho API polling: chỉ đọc các cột trạng thái cần thiết, không gọi `users_map()`, dữ liệu Rank, achievement, logo CLB hoặc dữ liệu tranh chấp.
- Polling trạng thái chỉ retry tối đa 2 lần để không giữ request quá lâu khi kết nối chập chờn.
- Giảm polling dự phòng khi Realtime đang kết nối từ 12 giây xuống 5 giây; tab ẩn dùng 20 giây.
- Chuyển cả nút Quay quân Xếp hạng và Giao hữu sang cơ chế fragment bất đồng bộ, không redirect/tải lại toàn trang.
- Gom phản hồi thao tác phòng qua `room_action_response()` và nhận diện cả HTMX lẫn fetch fragment để tránh hai nhánh logic chồng chéo.
- Nút Đá tiếp dùng phản hồi fragment; loại bỏ lượt kiểm tra phòng trùng lặp ở nhánh người thứ hai đồng ý.
- Nút Rời phòng trả redirect chuyên dụng cho fetch/HTMX, tránh fetch theo redirect rồi submit lặp lần hai.
- Cập nhật bộ xử lý form để đọc `X-RZ-Redirect`/`HX-Redirect`.
- Đặt Đá tiếp và Rời phòng nằm ngang cạnh nhau.
- Hạ thêm tên người chơi, dòng Rank và khu vực logo CLB trong khung Rank; mobile dùng độ dịch nhỏ hơn.
- Không thay đổi schema Supabase, công thức RP hoặc cấu trúc bảng dữ liệu.

# V1.10.62 — Điều khiển sau trận và căn chỉnh khung Rank

- Khi phòng chuyển sang `confirmed`, đưa hai nút **Đá tiếp** và **Rời phòng** lên khu vực giữa hai thẻ người chơi cho cả chủ phòng và khách.
- Các form sau trận dùng cùng cơ chế cập nhật fragment (`data-room-async`) nên không tải lại toàn bộ trang.
- Loại bỏ cụm nút trùng ở phần Điều khiển phòng để tránh hai nguồn thao tác chồng chéo.
- Hạ nhẹ tên người chơi, dòng Rank và khu vực logo CLB trong khung Rank; có mức dịch riêng cho mobile.
- Không thay đổi cơ chế tính RP, xác nhận tỷ số, Realtime hoặc cấu trúc dữ liệu Supabase.

# V1.10.61 — Đồng bộ phòng ổn định, không phụ thuộc HTMX CDN

- Sửa lỗi phía đối thủ không thấy tỷ số mới cho đến khi F5.
- Thay cơ chế tải fragment phụ thuộc `htmx.ajax()` bằng `fetch()` nguyên bản; HTMX chỉ còn là lớp tăng cường giao diện.
- Gom Realtime, polling và cập nhật fragment vào một bộ điều phối duy nhất để tránh request chồng chéo.
- Realtime cập nhật ngay khung `#roomDynamicState`; polling 2 giây khi chưa có Realtime và 12 giây khi Realtime đã kết nối để làm lớp bảo hiểm.
- Thêm chống request trùng, hàng đợi một lần refresh tiếp theo và không ghi đè khi người dùng đang nhập tỷ số.
- Gửi tỷ số và xác nhận kết quả dùng fetch tại chỗ; nếu fetch lỗi mới fallback về submit HTML chuẩn.
- Thêm `Cache-Control: no-store` cho API trạng thái và fragment phòng để tránh trình duyệt/CDN trả nội dung cũ.
- Xóa cache phòng/trận ngay sau xác nhận kết quả.
- Không thay đổi schema Supabase và không thay đổi công thức RP.

# V1.10.60 — Phòng đấu cập nhật từng phần bằng HTMX + Supabase Realtime

## Mục tiêu
- Loại bỏ việc tải lại toàn bộ trang khi trạng thái phòng thay đổi.
- Rút ngắn thời gian người còn lại nhận tỷ số và nút xác nhận.
- Giữ Supabase Realtime làm kênh thông báo chính; polling chỉ là dự phòng.

## Thay đổi chính
- Tạo `templates/partials/room_dynamic_state.html` làm khung trạng thái động của phòng đấu.
- Tạo endpoint `GET /room/<room_id>/state-fragment` để truy xuất lại đúng dữ liệu phòng từ Supabase và chỉ render phần HTML cần thay.
- Form **Gửi Kết Quả** dùng HTMX, khóa nút trong lúc gửi và thay riêng `#roomDynamicState`.
- Form **Xác Nhận** dùng HTMX, không redirect và không tải lại toàn trang.
- Backend gửi/xác nhận tỷ số vẫn dùng đúng logic kiểm tra quyền, trạng thái trận, cập nhật `matches`, `match_rooms` và tính RP hiện có.
- Thông báo thành công/lỗi của hai thao tác được trả ngay trong fragment.
- Supabase Realtime của `match_rooms` gọi cập nhật fragment sau khoảng 80 ms thay vì gọi `window.location.reload()`.
- Polling dự phòng khi Realtime chưa kết nối giảm từ 6 giây xuống 3 giây.
- Khi Realtime đã kết nối, polling kiểm tra an toàn giãn từ 45 giây lên 90 giây để giảm request thừa.
- Sau mỗi lần HTMX thay fragment, bộ đếm thời gian và `state_key` được khởi tạo lại đúng trạng thái mới.
- Nâng `APP_VERSION` lên `V1.10.60`.

## Không thay đổi
- Không thay schema hoặc tạo bảng Supabase mới.
- Không thay logic cộng/trừ RP.
- Chat phòng và Presence vẫn ưu tiên Supabase Realtime.
- Các form vẫn giữ `method` và `action` thông thường để fallback khi HTMX/CDN không tải được.

## Kiểm tra
- `app.py` biên dịch Python thành công.
- Toàn bộ template Jinja parse thành công.
- Không còn `window.location.reload()` trong `room_detail.html`.
