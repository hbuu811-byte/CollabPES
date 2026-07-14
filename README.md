## V1.10.41_PROFILE_BANNER_VISIBILITY_HOTFIX_NO_SQL

**Mục tiêu:** làm banner hồ sơ đã trang bị hiển thị rõ hơn, không còn bị lớp phủ tối che gần hết ảnh.

**Thay đổi:**
- Giảm mạnh overlay đen trên `.rzp-profile-hero.has-profile-banner::after`.
- Tăng `brightness/contrast/saturate` cho ảnh banner nền.
- Tăng nhẹ chiều cao hero hồ sơ để banner có thêm không gian hiển thị.
- Giữ độ đọc chữ bằng nền mờ nhẹ cho chip/rank và text shadow.
- Cập nhật cache CSS trong `templates/base.html` lên `?v=1.10.41`.
- `APP_VERSION` cập nhật lên `V1.10.41`.

**Không thay đổi:**
- Không cần SQL.
- Không đổi database.
- Không đụng Shop, mua vật phẩm, Kho đồ, ZCOIN, phòng đấu, BXH hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.41_PROFILE_BANNER_VISIBILITY_HOTFIX_NO_SQL`


## V1.10.40_INVENTORY_EQUIP_PROFILE_BANNER_NO_SQL

**Mục tiêu:** mở chức năng trang bị banner hồ sơ đã mua trong Kho đồ.

**Thay đổi:**
- Người chơi có thể vào `Kho đồ` và bấm `Trang bị` trên banner hồ sơ đã mua.
- Chỉ một banner hồ sơ được sử dụng tại một thời điểm.
- Có thể gỡ banner đang dùng bằng nút `Gỡ banner`.
- Trang hồ sơ sẽ hiển thị banner đang dùng làm nền phần hero hồ sơ.
- `APP_VERSION` cập nhật lên `V1.10.40`.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.40`.

**SQL:** không cần SQL mới nếu đã chạy V1.10.36, vì bảng `user_inventory` đã có sẵn cột `is_equipped`.

**Không thay đổi:**
- Không đổi logic mua Shop.
- Không đổi giá ZCOIN.
- Không đụng Gift Code, Điểm danh, BXH, Phòng đấu, Admin hoặc cơ chế cộng/trừ RP.

**Commit nên đặt khi upload GitHub:** `V1.10.40_INVENTORY_EQUIP_PROFILE_BANNER_NO_SQL`


## V1.10.37_SHOP_HIDE_MISSING_PRICE_BUTTON_NO_SQL

**Mục tiêu:** chỉnh giao diện Shop để không hiện dòng `Thiếu xxx` trên nút mua khi người chơi chưa đủ ZCOIN.

**Thay đổi:**
- Nút mua khi chưa đủ ZCOIN sẽ chỉ hiển thị giá vật phẩm, ví dụ `300 ZCOIN`, `700 ZCOIN`.
- Popup xem trước cũng dùng giá vật phẩm thay cho dòng `Thiếu xxx ZCOIN`.
- `APP_VERSION` cập nhật lên `V1.10.37`.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.37`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng luồng mua, Kho đồ, Gift Code, ZCOIN, Điểm danh, BXH, Admin, phòng đấu hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.37_SHOP_HIDE_MISSING_PRICE_BUTTON_NO_SQL`


## V1.10.36_SHOP_PURCHASE_INVENTORY_SAFE

**Mục tiêu:** chốt tab Nổi bật thành nơi hiển thị vật phẩm thật và mở bán thử nghiệm 5 banner hồ sơ bằng ZCOIN để người dùng có thể mua và lưu vào Kho đồ.

**Thay đổi:**
- Tab `Cửa Hàng → Nổi bật` không còn là placeholder; hiển thị 5 banner hồ sơ thật để mua nhanh.
- Tab `Cửa Hàng → Trang trí` tiếp tục hiển thị đầy đủ 5 banner hồ sơ.
- Người dùng có thể bấm `Mua ngay` để mua vật phẩm bằng ZCOIN.
- Nếu đã sở hữu vật phẩm, Shop hiển thị `Đã sở hữu` và không cho mua trùng.
- Nếu chưa đủ ZCOIN, Shop hiển thị số ZCOIN còn thiếu.
- Kho đồ `/inventory` hiển thị vật phẩm đã mua.
- Thêm SQL install/check/rollback cho bảng `user_inventory`, `shop_purchases` và function `buy_shop_item`.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.36`.
- `APP_VERSION` cập nhật lên `V1.10.36`.

**Cần chạy SQL:**
1. `docs/01_install_v1_10_36_shop_purchase_inventory.sql`
2. `docs/02_check_v1_10_36_shop_purchase_inventory.sql`

**Không thay đổi:**
- Chưa mở trang bị banner trực tiếp lên hồ sơ; bản này chỉ mua + lưu Kho đồ.
- Không đụng phòng đấu, BXH, Admin sửa trận, Gift Code, Điểm danh hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.36_SHOP_PURCHASE_INVENTORY_SAFE`


## V1.10.35_SHOP_PRICE_ROOM_HEADER_BALANCE_NO_SQL

**Mục tiêu:** chốt lại giá ZCOIN cho 5 banner hồ sơ trong Cửa Hàng và căn lại cụm avatar/tên/rank trong khung phòng đấu để không che đỉnh khung rank.

**Thay đổi:**
- Giá banner hồ sơ được điều chỉnh theo mức đã chốt:
  - Phòng Thay Đồ Elite: 300 ZCOIN.
  - Bậc Thầy Chiến Thuật: 700 ZCOIN.
  - Sân Đấu Neon: 1.400 ZCOIN.
  - Hành Lang Vinh Quang: 2.600 ZCOIN.
  - Đăng Quang Hoàng Kim: 4.500 ZCOIN.
- Cụm avatar / tên người chơi / tên rank trong phòng đấu được hạ xuống một chút để cân đối hơn với khung rank.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.35`.
- `APP_VERSION` cập nhật lên `V1.10.35`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Chưa mở mua thật / lưu kho / trang bị thật.
- Không đụng Gift Code, Điểm danh, BXH, Admin, phòng đấu logic hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.35_SHOP_PRICE_ROOM_HEADER_BALANCE_NO_SQL`


## V1.10.34_SHOP_PREVIEW_MODAL_HIDDEN_HOTFIX_NO_SQL

**Mục tiêu:** sửa lỗi popup xem trước vật phẩm trong Cửa Hàng tự hiện ngay khi vào trang và không đóng được.

**Nguyên nhân:** modal `#shopPreviewBackdrop` có thuộc tính `hidden`, nhưng CSS `.shop-preview-backdrop` lại đặt `display:grid`, làm một số trình duyệt vẫn render popup dù chưa bấm `Xem trước`.

**Thay đổi:**
- `static/style.css` thêm rule ép `.shop-preview-backdrop[hidden]` và `#shopPreviewBackdrop[hidden]` về `display:none!important`.
- `templates/shop.html` ép modal ẩn khi Shop vừa load, chỉ mở khi bấm `Xem trước`, và khi đóng sẽ set lại `hidden`.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.34`.
- `APP_VERSION` cập nhật lên `V1.10.34`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop catalog, ảnh vật phẩm, Gift Code, ZCOIN, Điểm danh, BXH, Admin, phòng đấu hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.34_SHOP_PREVIEW_MODAL_HIDDEN_HOTFIX_NO_SQL`


## V1.10.33_SHOP_ITEM_REPLACE_PREVIEW_NO_SQL

**Mục tiêu:** thay các vật phẩm mẫu cũ trong tab Trang trí của Cửa Hàng bằng bộ banner hồ sơ mới do người dùng cung cấp, đồng thời thêm chức năng xem trước trực tiếp ngay trong Shop.

**Thay đổi:**
- Thay 5 banner hồ sơ cũ bằng 5 ảnh banner mới trong `static/shop/profile_banners/`.
- Thay 5 icon vật phẩm cũ bằng 5 icon mới trong `static/shop/profile_banner_icons/`.
- `app.py` cập nhật catalog tĩnh `PROFILE_BANNER_SHOP_ITEMS` với tên vật phẩm, mô tả, độ hiếm và giá tương ứng.
- `templates/shop.html` đổi card Shop sang dạng vật phẩm rõ ràng hơn và thêm nút `Xem trước`.
- Thêm modal xem trước ngay trong Cửa Hàng để người chơi xem banner ở kích thước lớn, kèm icon, giá và độ hiếm.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.33`.
- `static/style.css` bổ sung layout cho nút preview và modal xem trước.
- `APP_VERSION` cập nhật lên `V1.10.33`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Chưa mở mua thật / lưu kho / trang bị thật.
- Không đụng Gift Code, ZCOIN, Điểm danh, BXH, Admin, phòng đấu hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.33_SHOP_ITEM_REPLACE_PREVIEW_NO_SQL`


## V1.10.32_HISTORY_SCORE_PERSPECTIVE_HOTFIX_NO_SQL

**Mục tiêu:** sửa lỗi lịch sử/hồ sơ hiển thị tỷ số không cùng góc nhìn với nhãn THẮNG/THUA.

**Nguyên nhân:** khi người đang xem là `player2`, app đã tính nhãn THẮNG/THUA theo đúng người xem, nhưng `score_display` vẫn giữ thứ tự gốc trong database là `player1 - player2`. Vì vậy có trường hợp nhìn thấy `6 - 2` nhưng lại hiện `THUA`.

**Thay đổi:**
- `decorate_match_for_view()` giờ hiển thị tỷ số theo góc nhìn của người được xem: `điểm của tôi - điểm đối thủ`.
- Nhãn `THẮNG`, `THUA`, `HÒA` và tỷ số sẽ khớp nhau.
- `APP_VERSION` cập nhật lên `V1.10.32`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không sửa dữ liệu lịch sử cũ.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.32_HISTORY_SCORE_PERSPECTIVE_HOTFIX_NO_SQL`


## V1.10.31_SHOP_PROFILE_BANNER_ASSETS_NO_SQL

**Mục tiêu:** tích hợp gói `PES_2026_PROFILE_BANNER_PACK_5` vào Cửa Hàng, tab Trang trí, để người chơi xem trước 5 banner hồ sơ đầu tiên.

**Thay đổi:**
- Thêm 5 banner WEBP vào `static/shop/profile_banners/`.
- Thêm 5 icon Shop PNG vào `static/shop/profile_banner_icons/`.
- Thêm preview pack và manifest JSON/CSV gốc để tiện quản lý tài nguyên.
- `app.py` thêm catalog tĩnh `PROFILE_BANNER_SHOP_ITEMS`.
- `templates/shop.html` hiển thị khu `Banner hồ sơ` trong tab `Trang trí` với ảnh, tên, độ hiếm và giá ZCOIN đề xuất.
- `static/style.css` thêm giao diện card banner trong Shop.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.31`.
- `APP_VERSION` cập nhật lên `V1.10.31`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Chưa mở mua/sử dụng banner thật; đây là bước tích hợp tài nguyên và hiển thị trong Shop trước.
- Không đụng Gift Code, ZCOIN, Điểm danh, BXH, Admin, phòng đấu hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.31_SHOP_PROFILE_BANNER_ASSETS_NO_SQL`


## V1.10.30_TOPBAR_ANNOUNCEMENT_FIT_HOTFIX_NO_SQL

**Mục tiêu:** sửa thanh thông báo trên topbar bị dài và lấn vào cụm icon bên phải.

**Thay đổi:**
- Thanh thông báo trên desktop không còn dùng `absolute center`, tránh che icon/ZCOIN/profile.
- Giới hạn chiều rộng thông báo theo khoảng trống còn lại giữa tiêu đề trang và cụm action bên phải.
- Thu gọn nhãn/thông điệp ở màn hình nhỏ để topbar sạch hơn.
- `templates/base.html` cập nhật cache CSS lên `?v=1.10.30`.
- `APP_VERSION` cập nhật lên `V1.10.30`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic phòng đấu.

**Commit nên đặt khi upload GitHub:** `V1.10.30_TOPBAR_ANNOUNCEMENT_FIT_HOTFIX_NO_SQL`


## V1.10.29_MOBILE_LAYOUT_SIDEBAR_SPACE_HOTFIX_NO_SQL

**Mục tiêu:** sửa lỗi mobile bị khoảng trống lớn phía trên khiến Dashboard/topbar bị đẩy xuống dưới.

**Nguyên nhân:** sidebar mobile đang bị `transform` ẩn sang trái nhưng vẫn chiếm layout flow, tạo khoảng trắng lớn trước nội dung chính.

**Thay đổi:**
- Sidebar mobile chuyển sang `position: fixed` để không chiếm chiều cao trang.
- Nút ☰ vẫn mở/đóng sidebar như cũ.
- Căn lại nhẹ topbar mobile cho icon, ZCOIN và profile gọn hơn.
- Cập nhật cache CSS trong `templates/base.html` lên `?v=1.10.29`.
- `APP_VERSION` cập nhật lên `V1.10.29`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic phòng đấu.

**Commit nên đặt khi upload GitHub:** `V1.10.29_MOBILE_LAYOUT_SIDEBAR_SPACE_HOTFIX_NO_SQL`


## V1.10.28_ROOM_RANK_FRAME_CARD_BACKGROUND_CLEANUP_NO_SQL

**Mục tiêu:** bỏ hẳn nền xanh/đỏ phía sau 2 ô người chơi trong phòng đấu, chỉ giữ khung rank làm chủ đạo.

**Thay đổi:**
- `static/style.css` override nền `room-team-card.home` và `room-team-card.away` thành trong suốt.
- Bỏ border/box-shadow ngoài của 2 card người chơi.
- Tắt lớp overlay nền `room-team-card::after`.
- Tăng nhẹ độ nổi của ảnh khung rank để tổng thể sạch và chuyên nghiệp hơn.
- `APP_VERSION` cập nhật lên `V1.10.28`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.28_ROOM_RANK_FRAME_CARD_BACKGROUND_CLEANUP_NO_SQL`


## V1.10.27_ROOM_RANK_FRAME_LAYOUT_HOTFIX_NO_SQL

**Mục tiêu:** chỉnh lại bố cục khung rank trong phòng đấu để avatar, tên người chơi, rank và phần chân khung cân đối hơn.

**Thay đổi:**
- `templates/room_detail.html` đổi avatar phòng đấu sang kích thước phù hợp hơn và đưa tên giải xuống phần chân khung.
- `static/style.css` căn lại vị trí khung rank, avatar, tên người chơi, dòng rank, logo đội, tên đội và footer giải đấu.
- `APP_VERSION` cập nhật lên `V1.10.27`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.27_ROOM_RANK_FRAME_LAYOUT_HOTFIX_NO_SQL`



## V1.10.26_ROOM_RANK_FRAME_ASSETS_NO_SQL

**Mục tiêu:** thêm 10 ảnh khung rank mới vào phòng đấu, tự động hiển thị theo rank hiện tại của từng người chơi.

**Thay đổi:**
- Thêm `static/rank_frames/` gồm 10 ảnh PNG: Gà, Non, Báo Thủ, Mới Tập Chơi, Bán Chuyên, Chuyên Nghiệp, Đẳng Cấp, Siêu Sao, Huyền Thoại, GOAT.
- `templates/room_detail.html` hiển thị khung rank phía sau card chủ phòng và khách.
- `static/style.css` bổ sung CSS đặt khung rank như lớp trang trí, không ảnh hưởng logic phòng đấu.
- `APP_VERSION` cập nhật lên `V1.10.26`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Shop, Gift Code, ZCOIN, Điểm danh, BXH, Admin hoặc logic tính điểm.

**Commit nên đặt khi upload GitHub:** `V1.10.26_ROOM_RANK_FRAME_ASSETS_NO_SQL`


## V1.10.25_SHOP_TAB_PAGE_NAVIGATION_NO_SQL

**Mục tiêu:** chỉnh Cửa Hàng thành dạng tab/danh mục riêng, không còn dùng anchor nhảy xuống section bên dưới.

**Thay đổi:**
- `/shop` nhận tham số `?tab=` để mở đúng danh mục: Nổi bật, Trang trí, Tiện ích, Lucky Box, Gift Code.
- Chỉ hiển thị nội dung của tab đang chọn.
- Gift Code chuyển thành tab riêng trong Cửa Hàng.
- Menu user trỏ Gift Code tới `/shop?tab=gift-code`.
- Cập nhật CSS active tab và khu nội dung tab.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Gift Code backend, ZCOIN, Điểm danh, phòng đấu, BXH hoặc Admin.

**Commit nên đặt khi upload GitHub:** `V1.10.25_SHOP_TAB_PAGE_NAVIGATION_NO_SQL`



## V1.10.24_SHOP_TEMPLATE_ITEMS_HOTFIX_NO_SQL

**Mục tiêu:** sửa lỗi 500 khi người dùng click vào Cửa Hàng sau bản V1.10.23.

**Nguyên nhân:** trong `templates/shop.html`, biến `section.items` bị Jinja hiểu là method `.items()` của dictionary, không phải danh sách item khung, dẫn đến lỗi `TypeError: 'builtin_function_or_method' object is not iterable`.

**Thay đổi:**
- Sửa `templates/shop.html` để dùng cú pháp key rõ ràng: `section['items']`.
- Cập nhật các key liên quan trong Shop: `key`, `icon`, `title`, `subtitle`.
- Cập nhật `APP_VERSION` lên `V1.10.24`.

**Không thay đổi:**
- Không cần SQL.
- Không thay đổi database.
- Không đụng Gift Code backend, ZCOIN, Điểm danh, BXH, phòng đấu, Admin sửa kết quả hoặc bật/tắt giao hữu.

**Commit nên đặt khi upload GitHub:** `V1.10.24_SHOP_TEMPLATE_ITEMS_HOTFIX_NO_SQL`

## V1.10.23_SHOP_SHELL_GIFT_CODE_SAFE

**Mục tiêu:** mở khung Cửa Hàng/Kho đồ trước và thêm Gift Code thật để Admin tặng ZCOIN cho người chơi.

**Thay đổi:**
- Thêm trang `/shop` dạng khung: Nổi bật, Trang trí, Tiện ích, Lucky Box.
- Thêm trang `/inventory` dạng khung Kho đồ, chưa có vật phẩm thật.
- Thêm lối vào Cửa Hàng ở sidebar và Kho đồ/Gift Code trong menu user.
- Thêm Gift Code: người dùng nhập mã trong Cửa Hàng để nhận ZCOIN.
- Thêm tab Admin `Gift Code` để tạo/tắt code và xem lịch sử đổi code.

**SQL:** cần chạy `docs/01_install_v1_10_23_shop_shell_gift_code.sql`, sau đó kiểm tra bằng `docs/02_check_v1_10_23_shop_shell_gift_code.sql`.

**Không thay đổi:**
- Không đụng logic rank, phòng đấu, BXH, random đội.
- Không đổi Điểm danh hằng ngày; Gift Code chỉ dùng chung ví ZCOIN.

**Commit nên đặt khi upload GitHub:** `V1.10.23_SHOP_SHELL_GIFT_CODE_SAFE`


## V1.10.22_ADMIN_MATCH_RESULT_DELTA_HOTFIX_NO_SQL

**Mục tiêu:** sửa lỗi Admin không lưu được kết quả trận đấu do `matches.delta1`/`delta2` bị ghi `NULL` trong khi database đang yêu cầu NOT NULL.

**Thay đổi:**
- Admin sửa kết quả dùng `delta1 = 0`, `delta2 = 0` làm giá trị tạm trước khi tính lại RP.
- Sau khi chuẩn bị tỷ số mới, hệ thống vẫn gọi `apply_match_result()` để tính delta thật và cập nhật BXH.
- Luồng xử lý tranh chấp Admin cũng được chỉnh để không chuyển thẳng sang confirmed trước khi tính RP.
- Rollback nội bộ khi sửa lỗi luôn restore delta thành số nguyên an toàn, không ghi NULL.

**Không thay đổi:**
- Không cần SQL/database migration.
- Không đổi công thức tính RP.
- Không đụng ZCOIN, Điểm danh, BXH, Dashboard, Players, menu user hoặc Kho đồ.

**Commit nên đặt khi upload GitHub:** `V1.10.22_ADMIN_MATCH_RESULT_DELTA_HOTFIX_NO_SQL`


## Update V1.10.19_FRIENDLY_TOGGLE_HARD_LOCK_NO_SQL

Mục tiêu: sửa dứt điểm tình trạng Admin tắt Giao hữu nhưng người chơi vẫn còn thấy hoặc bấm được chức năng Giao hữu trong phòng đấu.

Thay đổi chính:

- Admin / Hệ thống / Trận giao hữu dùng 2 nút rõ ràng: `Bật giao hữu` và `Tắt giao hữu`, tránh hiểu nhầm trạng thái công tắc.
- Trang phòng đấu đọc trạng thái Giao hữu mới nhất từ database khi render, hạn chế cache trạng thái cũ.
- Backend vẫn chặn request quay Giao hữu nếu Admin đã tắt, kể cả khi user còn tab cũ/cache.
- Nếu đang có trận Giao hữu cũ, chỉ cho kết thúc trận; không cho tự random tiếp khi hệ thống đã tắt Giao hữu.

SQL: không cần.
Rollback: rollback Vercel về bản trước, không cần restore Supabase.

# PES 2026 / Rank-PES-Collaboration

Đây là mốc phát triển chung của dự án PES 2026. Khi cập nhật source, luôn ghi rõ version, phạm vi thay đổi và có/không cần SQL để tránh người này update đè mất phần của người kia.

## Quy tắc update an toàn

1. Mỗi bản update phải có tên version rõ ràng, ví dụ: `V1.10.17_ROOM_CONFIRM_UI_HOTFIX_NO_SQL`.
2. Chỉ upload đúng file cần thay đổi, không upload nguyên thư mục source lồng nhau.
3. Không đưa các file sau lên GitHub hoặc ZIP update: `.env`, `__pycache__`, `*.pyc`, service role key, mật khẩu/API key thật.
4. Nếu bản update cần SQL, phải tách riêng trong `docs/` gồm file install, check và rollback khi cần.
5. Trước khi deploy bản có SQL hoặc chỉnh logic quan trọng, cần backup/ghi nhớ deployment ổn định hiện tại trên Vercel.
6. Nếu lỗi giao diện/code, rollback Vercel về deployment trước. Nếu lỗi liên quan database mới cân nhắc SQL rollback.

## Mốc version gần nhất

### V1.10.17_ROOM_CONFIRM_UI_HOTFIX_NO_SQL

- Sửa lỗi giao diện phòng đấu khi trận đang chờ xác nhận kết quả.
- Tỷ số đã nhập như `1 - 0` được hiển thị lớn, căn giữa, không bị dính vào nút xác nhận/tranh chấp.
- Không thay đổi database.
- Không cần SQL.
- File chính thay đổi: `static/style.css`, `app.py`, `Log.md`, `README.md`, `docs/update_v1_10_17_room_confirm_ui_hotfix_no_sql.txt`.

### V1.10.16_ROOM_SCORE_FRIENDLY_TOGGLE_NO_SQL

- Khôi phục tỷ số `0 - 0` ở giữa phòng đấu khi trận đang thi đấu.
- Thêm công tắc Admin bật/tắt trận giao hữu.
- Không cần SQL.

### V1.10.15_MERGE_LEAGUE_LOGOS_DAILY_CHECKIN_SAFE

- Gộp logo giải đấu trong phòng đấu với hệ thống ZCOIN/Điểm danh.
- Giữ điểm danh hằng ngày 80–150 ZCOIN, popup nhận thưởng và confetti.

### V1.10.14_PROFILE_DAILY_CHECKIN_SAFE

- Thêm ZCOIN thật và Điểm danh hằng ngày trong Hồ sơ cá nhân.
- Có SQL install/check/rollback trong `docs/`.

## Update V1.10.18_ROOM_SCORE_INPUT_LEAGUE_LOGO_HOTFIX_NO_SQL

- Mục tiêu: hotfix nhỏ cho phòng đấu, không thay đổi database.
- Làm chữ khu nhập kết quả trận đấu lớn hơn, đậm hơn, input dễ thao tác hơn.
- Bổ sung cơ chế fallback logo giải đấu, ưu tiên sửa các biến thể Ligue 1 và các tên giải dễ lệch định dạng.
- Thêm fallback khi logo đội/giải bị lỗi URL để không hiện icon ảnh lỗi.
- Không đụng ZCOIN, Điểm danh, BXH, Dashboard, Players, logic random đội hoặc tính điểm RP.
- Không cần SQL. Rollback: quay lại deployment V1.10.17 trên Vercel nếu cần.

### Quy tắc phối hợp update

- Mỗi bản update phải có version rõ ràng.
- Ghi chú thay đổi vào README.md, Log.md và docs/.
- Chỉ sửa đúng phạm vi tính năng cần sửa.
- Không upload .env, __pycache__, *.pyc.
- Nếu có SQL phải tách install/check/rollback và chỉ chạy khi đã thống nhất.


## V1.10.20_TOPBAR_ZCOIN_BALANCE_NO_SQL

**Mục tiêu:** hiển thị số dư ZCOIN ngay trên thanh topbar cạnh khu thông báo, để người chơi nhìn thấy số dư ở mọi trang.

**Thay đổi:**
- Thêm pill ZCOIN trên topbar.
- Pill ZCOIN trỏ về `Hồ sơ cá nhân → ZCOIN`.
- Cập nhật CSS responsive cho desktop/mobile.

**Không thay đổi:**
- Không đụng SQL/database.
- Không đụng logic điểm danh.
- Không đụng phòng đấu, BXH, lịch sử, Players, Admin.

**Commit nên đặt khi upload GitHub:** `V1.10.20_TOPBAR_ZCOIN_BALANCE_NO_SQL`


## V1.10.21_TOPBAR_ZCOIN_LOGO_NO_SQL

**Mục tiêu:** thay icon ZCOIN dạng emoji trên topbar bằng logo ZCOIN riêng do dự án cung cấp.

**Thay đổi:**
- Thêm asset `static/zcoin-logo.png`.
- Topbar ZCOIN sử dụng logo mới thay cho icon emoji.
- CSS tối ưu kích thước logo trong desktop/mobile.

**Không thay đổi:**
- Không đụng SQL/database.
- Không đụng logic điểm danh/ZCOIN.
- Không đụng phòng đấu, BXH, lịch sử, Players, Admin.

**Commit nên đặt khi upload GitHub:** `V1.10.21_TOPBAR_ZCOIN_LOGO_NO_SQL`
