-- Kiểm tra sau khi chạy SQL V1.10.23.
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('gift_codes', 'gift_code_redemptions', 'zcoin_transactions')
order by table_name;

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'gift_codes'
order by ordinal_position;

select proname
from pg_proc
where proname = 'redeem_gift_code';
