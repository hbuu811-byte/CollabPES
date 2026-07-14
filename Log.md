## V1.10.41_PROFILE_BANNER_VISIBILITY_HOTFIX_NO_SQL

- Hotfix hiển thị banner hồ sơ sau khi trang bị: giảm lớp phủ tối quá mạnh khiến banner bị mờ/không thấy rõ.
- Tăng độ sáng, tương phản và độ nổi của ảnh banner nền trong hồ sơ.
- Giữ khả năng đọc chữ bằng chip/rank có nền mờ nhẹ thay vì phủ tối toàn bộ banner.
- Cập nhật cache CSS lên `?v=1.10.41`.
- Không cần SQL, không đổi database, không đụng Shop/Kho đồ/ZCOIN/phòng đấu.
- Rollback: quay lại deployment V1.10.40 nếu cần.


## V1.10.40_INVENTORY_EQUIP_PROFILE_BANNER_NO_SQL

- Mở chức năng trang bị banner hồ sơ đã mua trong Kho đồ.
- Thêm route `/inventory/equip/<inventory_id>` để bật `is_equipped` cho banner hồ sơ được chọn.
- Thêm route `/inventory/unequip/profile-banner` để gỡ banner đang dùng.
- Profile hero đọc banner đang dùng từ `user_inventory` và hiển thị làm background.
- Kho đồ hiển thị trạng thái `Đang sử dụng` cho vật phẩm đang trang bị.
- Không cần SQL mới nếu đã chạy V1.10.36.
- Không đụng Shop purchase, Gift Code, Điểm danh, BXH, Phòng đấu, Admin hoặc logic RP.
- Rollback: quay lại V1.10.39 nếu cần.


## V1.10.37_SHOP_HIDE_MISSING_PRICE_BUTTON_NO_SQL

- Chỉnh giao diện Cửa Hàng theo yêu cầu: không còn hiển thị `Thiếu xxx` trên nút mua vật phẩm.
- Khi người chơi chưa đủ ZCOIN, nút disabled sẽ hiển thị lại đúng giá vật phẩm, ví dụ `300 ZCOIN`.
- Popup xem trước cũng đổi nút disabled sang giá vật phẩm, không hiển thị số ZCOIN còn thiếu.
- Không cần SQL, không đổi database, không đụng luồng mua vật phẩm hoặc Kho đồ.
- File thay đổi: `app.py`, `templates/base.html`, `templates/shop.html`, `README.md`, `Log.md`, `docs/update_v1_10_37_shop_hide_missing_price_button_no_sql.txt`.
- Rollback: quay lại deployment V1.10.36 nếu cần.


## V1.10.36_SHOP_PURCHASE_INVENTORY_SAFE

- Mở bán thử nghiệm 5 banner hồ sơ trong Cửa Hàng bằng ZCOIN.
- Tab Nổi bật đã hiển thị vật phẩm thật thay vì các ô placeholder cũ.
- Người chơi có thể mua vật phẩm; hệ thống trừ ZCOIN, ghi `zcoin_transactions`, ghi `shop_purchases` và thêm vật phẩm vào `user_inventory`.
- Kho đồ `/inventory` hiển thị danh sách vật phẩm đã sở hữu.
- Bảo vệ mua trùng cùng một vật phẩm bằng unique `(user_id, item_code)` và kiểm tra trong function `buy_shop_item`.
- Nếu chưa chạy SQL, Shop vẫn xem được vật phẩm nhưng khóa nút mua và hiển thị cảnh báo cần cài SQL.
- Không mở trang bị banner vào hồ sơ ở bản này để giữ an toàn giao diện profile hiện tại.
- File thay đổi: `app.py`, `templates/base.html`, `templates/shop.html`, `templates/inventory.html`, `static/style.css`, `README.md`, `Log.md`, `docs/01_install_v1_10_36_shop_purchase_inventory.sql`, `docs/02_check_v1_10_36_shop_purchase_inventory.sql`, `docs/99_rollback_v1_10_36_shop_purchase_inventory.sql`, `docs/update_v1_10_36_shop_purchase_inventory_safe.txt`.
- Rollback: rollback code về V1.10.35; chỉ chạy `99_rollback` nếu thật sự muốn xóa dữ liệu mua/Kho đồ đã phát sinh.


## V1.10.35_SHOP_PRICE_ROOM_HEADER_BALANCE_NO_SQL

- Chốt lại giá ZCOIN cho 5 banner hồ sơ trong Cửa Hàng theo mức cân bằng với điểm danh 80–150 ZCOIN/ngày.
- Giá mới: 300 / 700 / 1.400 / 2.600 / 4.500 ZCOIN.
- Hạ cụm avatar, tên người chơi, tên rank và trạng thái sẵn sàng trong khung phòng đấu xuống nhẹ để không che phần đỉnh khung rank.
- Cập nhật cache CSS trong `templates/base.html` lên `?v=1.10.35`.
- Không cần SQL, không đổi database, không mở mua thật/kho đồ/trang bị thật.
- File thay đổi: `app.py`, `templates/base.html`, `static/style.css`, `README.md`, `Log.md`, `docs/update_v1_10_35_shop_price_room_header_balance_no_sql.txt`.
- Rollback: quay lại deployment V1.10.34 nếu cần.


## V1.10.34_SHOP_PREVIEW_MODAL_HIDDEN_HOTFIX_NO_SQL

- Hotfix lỗi vào Cửa Hàng thì popup xem trước vật phẩm tự hiện dù người dùng chưa bấm `Xem trước`.
- Sửa lỗi nút dấu X / nút Đóng không tắt được popup do CSS vẫn giữ `display:grid` trên element có `hidden`.
- Thêm CSS bắt buộc ẩn modal khi có `hidden` và chỉ hiển thị khi remove `hidden`.
- JS Shop được bổ sung bước ép modal về trạng thái ẩn khi trang vừa load, đồng thời set/remove `hidden` rõ ràng khi mở/đóng preview.
- Cập nhật cache CSS trong `templates/base.html` lên `?v=1.10.34`.
- Không cần SQL, không đổi database, không đụng catalog vật phẩm/ảnh/Gift Code/ZCOIN/Điểm danh/BXH/Admin/phòng đấu.
- File thay đổi: `app.py`, `templates/base.html`, `templates/shop.html`, `static/style.css`, `README.md`, `Log.md`, `docs/update_v1_10_34_shop_preview_modal_hidden_hotfix_no_sql.txt`.
- Rollback: quay lại deployment V1.10.33 nếu cần.


## V1.10.33_SHOP_ITEM_REPLACE_PREVIEW_NO_SQL

- Thay toàn bộ vật phẩm banner mẫu cũ trong Cửa Hàng / Trang trí bằng bộ ảnh mới người dùng cung cấp.
- Thêm 5 banner hồ sơ mới và 5 icon vật phẩm mới, giữ cấu trúc Shop gọn và chuyên nghiệp hơn.
- Card vật phẩm trong Shop giờ có nút `Xem trước` để mở popup preview trực tiếp.
- Preview hiển thị ảnh banner lớn, icon vật phẩm, tên, độ hiếm, giá ZCOIN và mockup tên người chơi.
- Cập nhật cache CSS trong `templates/base.html` lên `?v=1.10.33` để tránh trình duyệt giữ style cũ.
- Không cần SQL, không đổi database, chưa mở chức năng mua/sở hữu/trang bị thật.
- File thay đổi: `app.py`, `templates/base.html`, `templates/shop.html`, `static/style.css`, `static/shop/profile_banners/*`, `static/shop/profile_banner_icons/*`, `README.md`, `Log.md`, `docs/update_v1_10_33_shop_item_replace_preview_no_sql.txt`.
- Rollback: quay lại deployment V1.10.32 nếu cần.


## V1.10.32_HISTORY_SCORE_PERSPECTIVE_HOTFIX_NO_SQL

- Hotfix lỗi hiển thị trong lịch sử/hồ sơ: tỷ số đang hiển thị theo thứ tự database `player1 - player2`, trong khi nhãn THẮNG/THUA hiển thị theo góc nhìn người đang xem.
- Khi người xem là `player2`, tỷ số giờ được đảo về đúng dạng `điểm của người xem - điểm đối thủ`.
- Ví dụ: nếu người được xem thắng 6-2 thì sẽ hiện `6 - 2` và `THẮNG`; nếu thua thì hiện theo điểm của người đó và `THUA`.
- Không cần SQL, không đổi database, không sửa dữ liệu trận cũ.
- File thay đổi: app.py, README.md, Log.md, docs/update_v1_10_32_history_score_perspective_hotfix_no_sql.txt.
- Rollback: quay lại deployment V1.10.31 nếu cần.


## V1.10.31_SHOP_PROFILE_BANNER_ASSETS_NO_SQL

- Tích hợp gói `PES_2026_PROFILE_BANNER_PACK_5` vào app.
- Thêm 5 banner hồ sơ đầu tiên: Phòng Thay Đồ, Chiến Thuật Gia, Derby Neon, Phòng Truyền Thống, Đăng Quang.
- Cửa Hàng / Trang trí hiển thị card banner với ảnh preview, icon, độ hiếm và giá ZCOIN đề xuất.
- Chưa mở chức năng mua/sử dụng banner thật, để tránh thay đổi database và logic Kho đồ khi chưa chốt hệ thống vật phẩm.
- Không cần SQL, không đổi database, không đụng Gift Code/ZCOIN/Điểm danh/BXH/Admin/phòng đấu.
- Rollback: quay lại deployment V1.10.30 nếu cần.


## V1.10.30_TOPBAR_ANNOUNCEMENT_FIT_HOTFIX_NO_SQL

- Hotfix thanh thông báo trên topbar bị dài/lấn sát cụm icon bên phải.
- Đưa announcement mount trên desktop về layout flex bình thường, không còn absolute center dễ đè lên icon.
- Giới hạn chiều rộng thanh thông báo và thu gọn label/marquee theo breakpoint.
- Cập nhật cache CSS lên `?v=1.10.30` để trình duyệt nhận style mới.
- Không cần SQL, không đổi database, không đụng Shop/Gift Code/ZCOIN/Điểm danh/BXH/Admin/Phòng đấu.
- Rollback: quay lại deployment V1.10.29 nếu cần.


## V1.10.29_MOBILE_LAYOUT_SIDEBAR_SPACE_HOTFIX_NO_SQL

- Hotfix lỗi mobile: mở app trên điện thoại bị trống một khoảng lớn phía trên, topbar/dashboard bị đẩy xuống dưới.
- Nguyên nhân là sidebar mobile bị transform ẩn nhưng vẫn chiếm chiều cao trong layout.
- Sửa bằng cách đặt `.player-sidebar` về `position: fixed` ở mobile, không còn chiếm layout flow.
- Căn lại nhẹ topbar mobile và cập nhật cache CSS trong `base.html` lên `?v=1.10.29`.
- Không cần SQL, không đổi database, không đụng Shop/Gift Code/ZCOIN/Điểm danh/BXH/Admin.
- Rollback: quay lại deployment V1.10.28 nếu cần.


## V1.10.28_ROOM_RANK_FRAME_CARD_BACKGROUND_CLEANUP_NO_SQL

- Hotfix giao diện phòng đấu: bỏ hẳn nền xanh/đỏ phía sau 2 ô người chơi.
- Chỉ giữ khung rank làm lớp hiển thị chính để giao diện sạch hơn và chuyên nghiệp hơn.
- Tắt border, box-shadow ngoài và overlay nền của `room-team-card`.
- Tăng nhẹ độ nổi của ảnh khung rank sau khi bỏ nền màu.
- Không cần SQL, không đổi database, không đụng Shop/Gift Code/ZCOIN/Điểm danh/BXH/Admin.
- Rollback: quay lại deployment V1.10.27 nếu cần.


## V1.10.27_ROOM_RANK_FRAME_LAYOUT_HOTFIX_NO_SQL

- Hotfix lại layout khung rank trong phòng đấu sau bản V1.10.26.
- Avatar được căn lại gần huy hiệu trên của khung để nhìn cân đối hơn.
- Tên người chơi và dòng rank được thu/phóng và canh lại để không bị lệch hoặc chèn vào nhau.
- Phần nameplate dưới của khung nay hiển thị tên giải đấu để tổng thể khớp hơn, không còn khoảng trống nhìn lạc vị trí.
- Không cần SQL, không đổi database, không đụng Shop/Gift Code/ZCOIN/Điểm danh/BXH/Admin.
- Rollback: quay lại deployment V1.10.26 nếu cần.



## V1.10.26_ROOM_RANK_FRAME_ASSETS_NO_SQL

- Thêm 10 ảnh khung rank mới do người dùng cung cấp vào `static/rank_frames/`.
- Map ảnh theo 10 rank hiện tại: Gà, Non, Báo Thủ, Mới Tập Chơi, Bán Chuyên, Chuyên Nghiệp, Đẳng Cấp, Siêu Sao, Huyền Thoại, GOAT.
- Phòng đấu hiển thị khung rank phía sau card chủ phòng/khách theo `room.host_rank_info.slug` và `room.guest_rank_info.slug`.
- Không cần SQL, không đổi database, không đụng Shop/Gift Code/ZCOIN/Điểm danh/BXH/Admin.
- Rollback: quay lại deployment V1.10.25 nếu cần.


## V1.10.23_SHOP_SHELL_GIFT_CODE_SAFE

- Thêm khung Cửa Hàng `/shop` với các khu: Nổi bật, Trang trí, Tiện ích, Lucky Box.
- Thêm khung Kho đồ `/inventory` để chuẩn bị quản lý vật phẩm sau này.
- Thêm Gift Code thật: user nhập mã trong Cửa Hàng để nhận ZCOIN.
- Thêm Admin tab `Gift Code`: tạo code, tắt/bật code, xem lịch sử đổi code.
- Thêm SQL install/check/rollback riêng trong `docs/`.
- Không thay đổi logic rank/phòng đấu/BXH/điểm danh.
- File thay đổi: app.py, templates/base.html, templates/shop.html, templates/inventory.html, templates/admin.html, static/style.css, README.md, Log.md, docs/*v1_10_23*.
- Commit khuyến nghị: `V1.10.23_SHOP_SHELL_GIFT_CODE_SAFE`.


## V1.10.22_ADMIN_MATCH_RESULT_DELTA_HOTFIX_NO_SQL

- Hotfix chức năng Admin sửa kết quả trận đấu.
- Sửa lỗi Supabase báo `null value in column "delta1" of relation "matches" violates not-null constraint`.
- Không còn ghi `delta1 = NULL` / `delta2 = NULL` khi chuẩn bị tính lại kết quả; dùng 0/0 tạm thời rồi ghi delta thật sau khi tính RP.
- Chỉnh thêm luồng Admin xử lý tranh chấp để apply kết quả đúng thứ tự, tránh confirmed sớm trước khi có delta thật.
- Không cần SQL, không đổi database schema, không đổi công thức tính RP.
- File thay đổi: app.py, README.md, Log.md, docs/update_v1_10_22_admin_match_result_delta_hotfix_no_sql.txt.
- Commit khuyến nghị: `V1.10.22_ADMIN_MATCH_RESULT_DELTA_HOTFIX_NO_SQL`.


## V1.10.19_FRIENDLY_TOGGLE_HARD_LOCK_NO_SQL

- Sửa triệt để nút bật/tắt trận Giao hữu trong Admin.
- Đổi giao diện Admin từ công tắc dễ hiểu nhầm sang 2 nút rõ ràng: Bật giao hữu / Tắt giao hữu.
- Room detail luôn đọc trạng thái Giao hữu mới nhất từ database, tránh cache làm user vẫn thấy card Giao hữu sau khi Admin tắt.
- Backend tiếp tục hard-block request quay đội Giao hữu khi Admin đã tắt.
- Khi Giao hữu đang tắt, card Giao hữu trong phòng đấu hiển thị trạng thái khóa; trận Giao hữu cũ chỉ còn cho kết thúc, không cho random tiếp.
- Không cần SQL, không đổi logic Rank/ZCOIN/Điểm danh/BXH.
- File thay đổi: app.py, templates/admin.html, templates/room_detail.html, static/style.css, README.md, Log.md, docs/update_v1_10_19_friendly_toggle_hard_lock_no_sql.txt.

# Log

## V1.10.17_ROOM_CONFIRM_UI_HOTFIX_NO_SQL

- Hotfix giao diện phòng đấu khi trạng thái đang chờ xác nhận kết quả.
- Sửa lỗi tỷ số đã nhập như `1 - 0` bị hiển thị nhỏ, lệch và dính vào hai nút `Xác Nhận` / `Không Đồng Ý`.
- Khôi phục layout tỷ số lớn ở giữa phòng đấu, hai nút xác nhận/tranh chấp nằm cùng hàng, cân đối như giao diện trước.
- Không thay đổi logic xác nhận kết quả, không thay đổi tính điểm, không đổi database.
- Không cần SQL.
- File thay đổi: `app.py`, `static/style.css`, `Log.md`, `README.md`, `docs/update_v1_10_17_room_confirm_ui_hotfix_no_sql.txt`.
- Rollback: quay lại deployment/commit V1.10.16 trên Vercel/GitHub, không cần restore Supabase.

## V1.10.14

- Cập nhật trực tiếp trên bản người dùng gửi `V1.10.13`.
- Chỉ sử dụng 11 logo league do người dùng cung cấp, không dùng lại logo tự tạo trước đó.
- Chuẩn hoá tất cả logo thành PNG 128x128, giữ đúng tỉ lệ, căn giữa và làm trong suốt phần nền ngoài khi có thể.
- Hiển thị logo nhỏ 22x22 cạnh tên giải trong phòng đấu, phù hợp vì logo giải chỉ là thông tin phụ.
- Thêm mapping Supabase cho Africa, Bundesliga, Europe, LaLiga EA Sports, Süper Lig, Serie BKT, Sky Bet Championship, South America, Serie A, Premier League và Ligue 1.
- Không cần SQL.


## V1.10.13_USER_DROPDOWN_LOGOUT_ONLY_NO_SQL

- Chuyển Đăng xuất vào menu xổ xuống của tên người dùng.
- Gỡ nút Đăng xuất riêng khỏi sidebar để sidebar gọn hơn.
- Không thay đổi database.
- Không cần SQL.
- File thay đổi: app.py, templates/base.html, static/style.css, Log.md, docs/update_v1_10_13_user_dropdown_logout_only_no_sql.txt.
- Rollback: quay lại deployment/commit trước, không cần restore database.

# Log

## V1.10.8

- Thay file `static/xucxac.png` bằng đúng ảnh xúc xắc mới người dùng cung cấp.
- Thêm tham số phiên bản vào URL ảnh để trình duyệt không dùng ảnh lỗi đã cache.
- Giữ xúc xắc đầy đủ màu sắc ở cả giao diện chủ phòng và đội khách.
- Đội khách hiển thị chữ `ĐỢI QUAY RANDOM ĐỘI`.
- Chủ phòng chưa thể quay vì khách chưa sẵn sàng sẽ thấy `ĐỢI KHÁCH SẴN SÀNG`.
- Chủ phòng đủ điều kiện vẫn thấy `QUAY RANDOM ĐỘI` và có thể bấm để quay.
- Cập nhật phiên bản thành `V1.10.8`.

## V1.10.10_PROFILE_UI_REORGANIZE_REPACK_NO_SQL

- Đóng gói lại bản tối ưu giao diện Hồ sơ cá nhân theo dạng root-only, tránh upload nhầm cả thư mục source lồng nhau.
- Sắp xếp lại Hồ sơ cá nhân thành các tab: Tổng quan, Thành tích, Lịch sử, ZCOIN, Điểm danh, Tài khoản.
- Tab ZCOIN và Điểm danh chỉ là khung giao diện, chưa kết nối database thật.
- Không cần SQL.
- Không thay đổi database.
- Cập nhật APP_VERSION thành V1.10.10 để dễ kiểm tra deploy.
- File thay đổi: app.py, templates/profile.html, static/style.css, Log.md, docs/update_v1_10_10_profile_ui_repack_no_sql.txt.
- Rollback: quay lại deployment/commit trước, không cần restore database.

## V1.10.11_PROFILE_TABS_FORCE_NO_SQL

- Repack riêng phần Hồ sơ cá nhân để bắt buộc cập nhật giao diện tab mới lên Production.
- Chỉ tác động khu vực hồ sơ: `templates/profile.html` và CSS hồ sơ trong `static/style.css`.
- `app.py` chỉ đổi `APP_VERSION` từ V1.10.10 sang V1.10.11 để dễ xác nhận deploy.
- Thêm tab: Tổng quan, Thành tích, Lịch sử, ZCOIN, Điểm danh, Tài khoản.
- Tab ZCOIN và Điểm danh chỉ là khung giao diện, chưa kết nối database thật.
- Không cần SQL.
- Không thay đổi database.
- Rollback: quay lại deployment/commit V1.10.10 trên Vercel/GitHub, không cần restore Supabase.


## V1.10.12_USER_DROPDOWN_MENU_NO_SQL

- Gom lối vào Hồ sơ cá nhân và Lịch sử khỏi sidebar vào menu xổ xuống ở tên người dùng trên topbar.
- Menu người dùng mới gồm: Quản lý tài khoản, Kho đồ (khung sắp phát triển), Điểm danh (khung trong hồ sơ), Lịch sử, Đăng xuất.
- Không thay đổi database, không thêm route mới, không sửa logic thi đấu/rank/phòng đấu.
- Chỉ cập nhật giao diện điều hướng và APP_VERSION.

## V1.10.15_MERGE_LEAGUE_LOGOS_DAILY_CHECKIN_SAFE

- Gộp bản update mới của bạn bạn với hệ thống Điểm danh/ZCOIN đã chạy thành công.
- Giữ phần logo giải đấu trong phòng đấu từ bản bạn bạn gửi.
- Giữ ví ZCOIN, điểm danh hằng ngày 80–150 ZCOIN, popup nhận thưởng và confetti.
- Nếu đã chạy SQL V1.10.14 và điểm danh hoạt động thì không cần chạy SQL thêm.
- File thay đổi: app.py, templates/base.html, templates/profile.html, templates/room_detail.html, static/style.css, Log.md, docs/*.
- Rollback: quay lại deployment trước; không cần restore database nếu chỉ lỗi code.
## V1.10.16_ROOM_SCORE_FRIENDLY_TOGGLE_NO_SQL

- Khôi phục hiển thị tỷ số 0 - 0 ở giữa phòng đấu khi trận đang thi đấu.
- Thêm cài đặt Admin bật/tắt chế độ trận giao hữu trong tab Hệ thống.
- Khi giao hữu bị tắt, phòng đấu chỉ cho quay trận Xếp hạng và không cho random tiếp giao hữu.
- Không cần SQL, không đổi database schema.


## V1.10.18_ROOM_SCORE_INPUT_LEAGUE_LOGO_HOTFIX_NO_SQL

- Tăng độ rõ của khu nhập kết quả trong phòng đấu: tiêu đề, label, input và nút gửi kết quả to/đậm hơn.
- Bổ sung alias/fallback logo giải đấu, đặc biệt cho Ligue 1 và các tên giải có biến thể dấu/khoảng trắng/gạch nối.
- Thêm fallback khi ảnh đội hoặc ảnh giải bị lỗi URL, tránh hiển thị icon ảnh lỗi.
- Không cần SQL.
- File thay đổi: app.py, templates/room_detail.html, static/style.css, README.md, Log.md, docs/update_v1_10_18_room_score_input_league_logo_hotfix_no_sql.txt.


## V1.10.20_TOPBAR_ZCOIN_BALANCE_NO_SQL

- Hiển thị số dư ZCOIN của người dùng ngay trên topbar, cạnh khu thông báo/chuông.
- Pill ZCOIN dẫn nhanh về Hồ sơ cá nhân → tab ZCOIN.
- Không thay đổi database, điểm danh, phòng đấu, BXH, admin hoặc logic tính điểm.
- Không cần SQL.
- Commit khuyến nghị trên GitHub: `V1.10.20_TOPBAR_ZCOIN_BALANCE_NO_SQL`.


## V1.10.21_TOPBAR_ZCOIN_LOGO_NO_SQL

- Thay icon ZCOIN dạng emoji trên topbar bằng logo ZCOIN riêng của dự án.
- Thêm file `static/zcoin-logo.png` đã được xử lý nền trong suốt để hiển thị gọn trên topbar.
- Không thay đổi database, điểm danh, ví ZCOIN, phòng đấu, BXH hoặc logic tính điểm.
- Không cần SQL.
- Commit khuyến nghị trên GitHub: `V1.10.21_TOPBAR_ZCOIN_LOGO_NO_SQL`.


## V1.10.24_SHOP_TEMPLATE_ITEMS_HOTFIX_NO_SQL

- Sửa lỗi 500 khi mở `/shop`: Jinja hiểu `section.items` là method dictionary `.items()` thay vì danh sách vật phẩm khung.
- Đổi template Shop sang cú pháp truy cập key rõ ràng: `section['items']`, `section['key']`, `section['icon']`, `section['title']`, `section['subtitle']`.
- Không thay đổi database, Gift Code, ZCOIN, Điểm danh, Admin, phòng đấu, BXH hoặc logic mua/bán.
- Không cần SQL.
- Rollback: quay lại deployment V1.10.23 nếu cần, không restore Supabase.
- Commit khuyến nghị trên GitHub: `V1.10.24_SHOP_TEMPLATE_ITEMS_HOTFIX_NO_SQL`.

## V1.10.25_SHOP_TAB_PAGE_NAVIGATION_NO_SQL

- Sửa trải nghiệm Cửa Hàng: các tab Nổi bật, Trang trí, Tiện ích, Lucky Box, Gift Code mở thành từng danh mục riêng bằng `?tab=...`.
- Không còn bấm tab rồi nhảy xuống section phía dưới bằng anchor.
- Chỉ render nội dung của tab đang chọn để giao diện Shop gọn và giống game store hơn.
- Gift Code được đưa thành tab riêng trong Cửa Hàng; menu user cập nhật sang `/shop?tab=gift-code`.
- Không cần SQL, không thay đổi database.
- Không đụng Gift Code backend, ZCOIN, Điểm danh, phòng đấu, BXH, Admin hoặc logic tính điểm.
- Commit khuyến nghị trên GitHub: `V1.10.25_SHOP_TAB_PAGE_NAVIGATION_NO_SQL`.
