-- V1.10.14_PROFILE_DAILY_CHECKIN_SAFE
-- Cài đặt ví ZCOIN + điểm danh hằng ngày.
-- An toàn dữ liệu: chỉ thêm cột/bảng/function mới, không xóa dữ liệu cũ.

create extension if not exists pgcrypto;

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

create table if not exists public.daily_checkins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users(id) on delete cascade,
  checkin_date date not null,
  reward_zcoin integer not null,
  streak_count integer not null default 1,
  created_at timestamptz not null default now(),
  unique(user_id, checkin_date)
);

create index if not exists daily_checkins_user_date_idx
  on public.daily_checkins(user_id, checkin_date desc);

alter table public.zcoin_transactions enable row level security;
alter table public.daily_checkins enable row level security;

do $$
begin
  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'zcoin_transactions' and policyname = 'zcoin_transactions_service_role_only'
  ) then
    create policy zcoin_transactions_service_role_only
      on public.zcoin_transactions
      for all
      using (false)
      with check (false);
  end if;

  if not exists (
    select 1 from pg_policies
    where schemaname = 'public' and tablename = 'daily_checkins' and policyname = 'daily_checkins_service_role_only'
  ) then
    create policy daily_checkins_service_role_only
      on public.daily_checkins
      for all
      using (false)
      with check (false);
  end if;
end $$;

create or replace function public.claim_daily_checkin(p_user_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_today date := (timezone('Asia/Ho_Chi_Minh', now()))::date;
  v_reward integer;
  v_prev_date date;
  v_prev_streak integer := 0;
  v_streak integer := 1;
  v_balance integer := 0;
  v_existing public.daily_checkins%rowtype;
begin
  -- Khóa user để chống double click / 2 request cùng lúc.
  select coalesce(zcoin_balance, 0)
    into v_balance
  from public.users
  where id = p_user_id
  for update;

  if not found then
    return jsonb_build_object('ok', false, 'error', 'user_not_found');
  end if;

  select * into v_existing
  from public.daily_checkins
  where user_id = p_user_id and checkin_date = v_today
  limit 1;

  if found then
    return jsonb_build_object(
      'ok', false,
      'already_claimed', true,
      'reward', v_existing.reward_zcoin,
      'streak', v_existing.streak_count,
      'balance_after', v_balance,
      'checkin_date', v_today
    );
  end if;

  select checkin_date, streak_count
    into v_prev_date, v_prev_streak
  from public.daily_checkins
  where user_id = p_user_id
  order by checkin_date desc
  limit 1;

  if v_prev_date = v_today - 1 then
    v_streak := coalesce(v_prev_streak, 0) + 1;
  else
    v_streak := 1;
  end if;

  v_reward := 80 + floor(random() * 71)::integer; -- 80..150
  v_balance := v_balance + v_reward;

  insert into public.daily_checkins(user_id, checkin_date, reward_zcoin, streak_count)
  values (p_user_id, v_today, v_reward, v_streak);

  update public.users
  set zcoin_balance = v_balance
  where id = p_user_id;

  insert into public.zcoin_transactions(
    user_id, amount, balance_after, transaction_type, source, description, metadata
  ) values (
    p_user_id,
    v_reward,
    v_balance,
    'daily_checkin',
    'daily_checkin',
    'Điểm danh hằng ngày',
    jsonb_build_object('checkin_date', v_today, 'streak', v_streak, 'reward_min', 80, 'reward_max', 150)
  );

  return jsonb_build_object(
    'ok', true,
    'already_claimed', false,
    'reward', v_reward,
    'streak', v_streak,
    'balance_after', v_balance,
    'checkin_date', v_today
  );
end;
$$;

grant execute on function public.claim_daily_checkin(uuid) to service_role;
