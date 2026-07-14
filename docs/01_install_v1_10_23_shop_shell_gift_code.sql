-- V1.10.23_SHOP_SHELL_GIFT_CODE_SAFE
-- Cài đặt Gift Code cho Cửa Hàng khung.
-- An toàn dữ liệu: chỉ thêm bảng/function/cột còn thiếu, không xóa dữ liệu cũ.

create extension if not exists pgcrypto;

-- Đảm bảo nền ZCOIN tồn tại nếu triển khai sang database mới.
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

create table if not exists public.gift_codes (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  reward_type text not null default 'zcoin',
  reward_zcoin integer not null default 0 check (reward_zcoin >= 0),
  max_redemptions integer not null default 1 check (max_redemptions > 0),
  redeemed_count integer not null default 0 check (redeemed_count >= 0),
  per_user_limit integer not null default 1 check (per_user_limit > 0),
  is_active boolean not null default true,
  expires_at timestamptz,
  created_by uuid references public.users(id) on delete set null,
  created_by_name text,
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists gift_codes_code_idx on public.gift_codes(code);
create index if not exists gift_codes_active_created_idx on public.gift_codes(is_active, created_at desc);

create table if not exists public.gift_code_redemptions (
  id uuid primary key default gen_random_uuid(),
  code_id uuid not null references public.gift_codes(id) on delete cascade,
  code text not null,
  user_id uuid not null references public.users(id) on delete cascade,
  reward_type text not null default 'zcoin',
  reward_zcoin integer not null default 0,
  balance_after integer not null default 0,
  redeemed_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists gift_code_redemptions_user_idx
  on public.gift_code_redemptions(user_id, redeemed_at desc);

create index if not exists gift_code_redemptions_code_idx
  on public.gift_code_redemptions(code_id, redeemed_at desc);

alter table public.gift_codes enable row level security;
alter table public.gift_code_redemptions enable row level security;

-- App server dùng service role; client public không được đọc/ghi trực tiếp các bảng này.
do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'gift_codes' and policyname = 'gift_codes_service_role_only'
  ) then
    create policy gift_codes_service_role_only
      on public.gift_codes
      for all
      using (false)
      with check (false);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'gift_code_redemptions' and policyname = 'gift_code_redemptions_service_role_only'
  ) then
    create policy gift_code_redemptions_service_role_only
      on public.gift_code_redemptions
      for all
      using (false)
      with check (false);
  end if;
end $$;

create or replace function public.redeem_gift_code(p_user_id uuid, p_code text)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_code text := upper(trim(coalesce(p_code, '')));
  v_gift public.gift_codes%rowtype;
  v_balance integer := 0;
  v_user_redeems integer := 0;
begin
  v_code := regexp_replace(v_code, '[^A-Z0-9_-]', '', 'g');

  if v_code = '' then
    return jsonb_build_object('ok', false, 'error', 'empty_code');
  end if;

  select * into v_gift
  from public.gift_codes
  where code = v_code
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'code_not_found');
  end if;

  if v_gift.is_active is not true then
    return jsonb_build_object('ok', false, 'error', 'inactive');
  end if;

  if v_gift.expires_at is not null and v_gift.expires_at < now() then
    return jsonb_build_object('ok', false, 'error', 'expired');
  end if;

  if coalesce(v_gift.redeemed_count, 0) >= coalesce(v_gift.max_redemptions, 1) then
    return jsonb_build_object('ok', false, 'error', 'sold_out');
  end if;

  select count(*) into v_user_redeems
  from public.gift_code_redemptions
  where code_id = v_gift.id and user_id = p_user_id;

  if v_user_redeems >= coalesce(v_gift.per_user_limit, 1) then
    return jsonb_build_object('ok', false, 'error', 'already_redeemed');
  end if;

  select coalesce(zcoin_balance, 0)
    into v_balance
  from public.users
  where id = p_user_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'user_not_found');
  end if;

  if v_gift.reward_type <> 'zcoin' then
    return jsonb_build_object('ok', false, 'error', 'unsupported_reward');
  end if;

  v_balance := v_balance + coalesce(v_gift.reward_zcoin, 0);

  update public.users
  set zcoin_balance = v_balance
  where id = p_user_id;

  update public.gift_codes
  set redeemed_count = coalesce(redeemed_count, 0) + 1,
      updated_at = now()
  where id = v_gift.id;

  insert into public.gift_code_redemptions(
    code_id, code, user_id, reward_type, reward_zcoin, balance_after, metadata
  ) values (
    v_gift.id,
    v_gift.code,
    p_user_id,
    v_gift.reward_type,
    coalesce(v_gift.reward_zcoin, 0),
    v_balance,
    jsonb_build_object('source', 'gift_code', 'note', v_gift.note)
  );

  insert into public.zcoin_transactions(
    user_id, amount, balance_after, transaction_type, source, description, metadata
  ) values (
    p_user_id,
    coalesce(v_gift.reward_zcoin, 0),
    v_balance,
    'gift_code',
    'gift_code',
    'Đổi gift code ' || v_gift.code,
    jsonb_build_object('gift_code_id', v_gift.id, 'code', v_gift.code)
  );

  return jsonb_build_object(
    'ok', true,
    'code', v_gift.code,
    'reward_type', v_gift.reward_type,
    'reward_zcoin', coalesce(v_gift.reward_zcoin, 0),
    'balance_after', v_balance
  );
end;
$$;

grant execute on function public.redeem_gift_code(uuid, text) to service_role;
