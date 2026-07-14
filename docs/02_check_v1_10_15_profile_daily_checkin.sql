-- Kiểm tra sau khi chạy SQL V1.10.15.
select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'users'
  and column_name = 'zcoin_balance';

select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('zcoin_transactions', 'daily_checkins')
order by table_name;

select proname
from pg_proc
where proname = 'claim_daily_checkin';
