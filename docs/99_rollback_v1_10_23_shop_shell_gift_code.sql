-- Rollback V1.10.23 nếu thật sự cần.
-- CẢNH BÁO: lệnh này xóa Gift Code và lịch sử đổi code đã phát sinh.
-- Không xóa zcoin_transactions / zcoin_balance vì đang dùng cho điểm danh.

drop function if exists public.redeem_gift_code(uuid, text);
drop table if exists public.gift_code_redemptions;
drop table if exists public.gift_codes;
