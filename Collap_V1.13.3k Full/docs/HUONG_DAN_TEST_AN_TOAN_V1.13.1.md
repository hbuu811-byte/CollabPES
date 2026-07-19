# Hướng dẫn test an toàn — PES Arena V1.13.1

## Nguyên tắc bắt buộc

Không dùng chung Supabase Production cho bản test. Hãy tạo một Supabase project riêng, ví dụ `pes-arena-test`, rồi dùng URL và Service Role Key của project đó cho Vercel Preview/Test.

## Biến môi trường của dự án Test

```env
APP_ENV=test
PES_ARENA_TEST_MODE=true
DATABASE_SAFETY_TOKEN=PES_ARENA_TEST_DATABASE
SUPABASE_URL=https://PROJECT-TEST.supabase.co
SUPABASE_SERVICE_ROLE_KEY=SERVICE_ROLE_KEY_CUA_PROJECT_TEST
FLASK_SECRET_KEY=CHUOI_BI_MAT_RIENG_CUA_BAN_TEST
```

Không sao chép `SUPABASE_URL` hoặc key của Production sang dự án Test.

## Quy trình đề xuất

1. Tạo Supabase project Test riêng.
2. Chạy toàn bộ migration SQL hiện có trên project Test.
3. Import 10–20 tài khoản giả bằng CSV mẫu.
4. Tạo một Vercel project riêng tên `pes-arena-test` hoặc dùng Preview branch nhưng gắn biến môi trường Test.
5. Kiểm tra banner vàng `PES ARENA TEST MODE` trên đầu trang.
6. Test phân quyền, tạo trận, sửa trận, hủy trận và tính lại RP.
7. Chỉ merge code sang Production; không chuyển dữ liệu Test sang Production.

## Bộ test tối thiểu

- Admin không có quyền: tab ẩn, nút ẩn, nhập URL trực tiếp nhận 403/chuyển hướng.
- Import CSV có `rank_points=-1000`: tài khoản cũ bị trừ đúng 1000 RP nhưng không xuống dưới 0.
- Trận thắng/thua: delta người thắng dương, người thua âm.
- Xác nhận lặp hai lần: RP chỉ thay đổi một lần.
- Hủy phòng có trận confirmed: RP và thống kê được hoàn tác trước khi trận chuyển cancelled.
- Hai Admin bấm tính lại RP cùng lúc: chỉ một tiến trình được chạy.
- Tính lại RP lỗi giữa chừng: snapshot người dùng và trạng thái trận được khôi phục.
