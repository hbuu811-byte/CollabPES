-- Rollback V1.10.15 nếu thật sự cần.
-- CẢNH BÁO: lệnh này xóa lịch sử ZCOIN và điểm danh đã phát sinh từ bản V1.10.15.
-- Chỉ chạy sau khi đã rollback code Vercel/GitHub và bạn chắc chắn muốn bỏ tính năng này.

drop function if exists public.claim_daily_checkin(uuid);
drop table if exists public.daily_checkins;
drop table if exists public.zcoin_transactions;

alter table public.users drop constraint if exists users_zcoin_balance_non_negative;
alter table public.users drop column if exists zcoin_balance;
