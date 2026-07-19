-- Kiểm tra sau khi chạy SQL V1.10.36.

select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in ('user_inventory', 'shop_purchases', 'zcoin_transactions')
order by table_name;

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'user_inventory'
order by ordinal_position;

select column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name = 'shop_purchases'
order by ordinal_position;

select proname
from pg_proc
where proname = 'buy_shop_item';
