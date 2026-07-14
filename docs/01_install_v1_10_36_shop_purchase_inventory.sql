-- V1.10.36_SHOP_PURCHASE_INVENTORY_SAFE
-- Bật mua vật phẩm Shop bằng ZCOIN và lưu vào Kho đồ.
-- An toàn dữ liệu: chỉ thêm bảng/function/cột còn thiếu, không xóa dữ liệu cũ.

create extension if not exists pgcrypto;

-- Đảm bảo nền ZCOIN tồn tại.
alter table public.users
  add column if not exists zcoin_balance integer not null default 0;

update public.users
set zcoin_balance = 0
where zcoin_balance is null;

do $$
begin
  if not exists (
    select 1 from pg_constraint where conname = 'users_zcoin_balance_non_negative'
  ) then
    alter table public.users
      add constraint users_zcoin_balance_non_negative check (zcoin_balance >= 0);
  end if;
end $$;

create table if not exists public.zcoin_transactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  amount integer not null,
  balance_after integer not null default 0,
  transaction_type text not null,
  source text not null default 'system',
  description text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists zcoin_transactions_user_created_idx
  on public.zcoin_transactions(user_id, created_at desc);

create table if not exists public.user_inventory (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  item_code text not null,
  item_name text not null,
  item_type text not null default 'profile_banner',
  rarity text,
  image_path text,
  icon_path text,
  quantity integer not null default 1 check (quantity > 0),
  is_equipped boolean not null default false,
  acquired_from text not null default 'shop',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, item_code)
);

create index if not exists user_inventory_user_created_idx
  on public.user_inventory(user_id, created_at desc);

create index if not exists user_inventory_user_type_idx
  on public.user_inventory(user_id, item_type);

create table if not exists public.shop_purchases (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  item_code text not null,
  item_name text not null,
  item_type text not null default 'profile_banner',
  rarity text,
  price_zcoin integer not null check (price_zcoin >= 0),
  purchase_status text not null default 'paid',
  balance_after integer not null default 0,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists shop_purchases_user_created_idx
  on public.shop_purchases(user_id, created_at desc);

create index if not exists shop_purchases_item_idx
  on public.shop_purchases(item_code, created_at desc);

alter table public.user_inventory enable row level security;
alter table public.shop_purchases enable row level security;

-- App server dùng service role; client public không được đọc/ghi trực tiếp các bảng này.
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'user_inventory' and policyname = 'user_inventory_service_role_only'
  ) then
    create policy user_inventory_service_role_only
      on public.user_inventory
      for all
      using (false)
      with check (false);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'shop_purchases' and policyname = 'shop_purchases_service_role_only'
  ) then
    create policy shop_purchases_service_role_only
      on public.shop_purchases
      for all
      using (false)
      with check (false);
  end if;
end $$;

create or replace function public.buy_shop_item(
  p_user_id uuid,
  p_item_code text,
  p_price integer,
  p_item_name text,
  p_item_type text default 'profile_banner',
  p_item_rarity text default null,
  p_item_image text default null,
  p_item_icon text default null,
  p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code text := trim(coalesce(p_item_code, ''));
  v_balance integer := 0;
  v_balance_after integer := 0;
  v_owned integer := 0;
  v_purchase_id uuid;
  v_inventory_id uuid;
begin
  v_code := regexp_replace(v_code, '[^a-zA-Z0-9_-]', '', 'g');

  if v_code = '' or coalesce(p_item_name, '') = '' then
    return jsonb_build_object('ok', false, 'error', 'item_not_available');
  end if;

  if coalesce(p_price, 0) <= 0 then
    return jsonb_build_object('ok', false, 'error', 'invalid_price');
  end if;

  select coalesce(zcoin_balance, 0)
    into v_balance
  from public.users
  where id = p_user_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'user_not_found');
  end if;

  select count(*)
    into v_owned
  from public.user_inventory
  where user_id = p_user_id and item_code = v_code;

  if coalesce(v_owned, 0) > 0 then
    return jsonb_build_object('ok', false, 'error', 'already_owned', 'balance_after', v_balance);
  end if;

  if v_balance < p_price then
    return jsonb_build_object(
      'ok', false,
      'error', 'not_enough_zcoin',
      'balance_after', v_balance,
      'missing', p_price - v_balance
    );
  end if;

  v_balance_after := v_balance - p_price;

  update public.users
  set zcoin_balance = v_balance_after
  where id = p_user_id;

  insert into public.shop_purchases(
    user_id, item_code, item_name, item_type, rarity, price_zcoin, purchase_status, balance_after, metadata
  ) values (
    p_user_id, v_code, p_item_name, coalesce(p_item_type, 'profile_banner'), p_item_rarity,
    p_price, 'paid', v_balance_after,
    coalesce(p_metadata, '{}'::jsonb) || jsonb_build_object('image_path', p_item_image, 'icon_path', p_item_icon)
  ) returning id into v_purchase_id;

  insert into public.user_inventory(
    user_id, item_code, item_name, item_type, rarity, image_path, icon_path, quantity, is_equipped, acquired_from, metadata
  ) values (
    p_user_id, v_code, p_item_name, coalesce(p_item_type, 'profile_banner'), p_item_rarity,
    p_item_image, p_item_icon, 1, false, 'shop',
    coalesce(p_metadata, '{}'::jsonb) || jsonb_build_object('purchase_id', v_purchase_id)
  ) returning id into v_inventory_id;

  insert into public.zcoin_transactions(
    user_id, amount, balance_after, transaction_type, source, description, metadata
  ) values (
    p_user_id,
    -p_price,
    v_balance_after,
    'shop_purchase',
    'shop',
    'Mua vật phẩm Shop: ' || p_item_name,
    jsonb_build_object(
      'purchase_id', v_purchase_id,
      'inventory_id', v_inventory_id,
      'item_code', v_code,
      'item_name', p_item_name,
      'item_type', coalesce(p_item_type, 'profile_banner'),
      'price_zcoin', p_price
    )
  );

  return jsonb_build_object(
    'ok', true,
    'item_code', v_code,
    'item_name', p_item_name,
    'price_zcoin', p_price,
    'balance_after', v_balance_after,
    'purchase_id', v_purchase_id,
    'inventory_id', v_inventory_id
  );
end;
$$;

grant execute on function public.buy_shop_item(uuid, text, integer, text, text, text, text, text, jsonb) to service_role;
