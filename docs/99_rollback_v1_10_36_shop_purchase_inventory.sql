-- Rollback V1.10.36 nếu thật sự cần.
-- CẢNH BÁO: lệnh này xóa lịch sử mua Shop và Kho đồ đã phát sinh từ V1.10.36.
-- Chỉ chạy sau khi đã rollback code Vercel/GitHub và chắc chắn muốn bỏ chức năng này.

drop function if exists public.buy_shop_item(uuid, text, integer, text, text, text, text, text, jsonb);
drop table if exists public.shop_purchases;
drop table if exists public.user_inventory;
