-- PES Arena v1.13.0 - nâng cấp quản trị
alter table public.users add column if not exists admin_permissions jsonb not null default '{}'::jsonb;
alter table public.matches add column if not exists created_by uuid null;
alter table public.matches add column if not exists host_user_id uuid null;
alter table public.matches add column if not exists rp_formula_version text null;
alter table public.matches add column if not exists rp_details jsonb null;
alter table public.matches add column if not exists updated_at timestamptz default now();

create table if not exists public.system_settings (
  setting_key text primary key,
  setting_value jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

insert into public.system_settings(setting_key, setting_value)
values ('admin_system_features', '{"friendly_enabled":true,"lobby_chat_enabled":true,"room_chat_enabled":true,"registration_codes_enabled":true,"announcements_enabled":true}'::jsonb)
on conflict (setting_key) do nothing;

create index if not exists idx_matches_created_at on public.matches(created_at);
create index if not exists idx_matches_status_created_at on public.matches(status, created_at);
