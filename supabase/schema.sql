-- Ejecutar en Supabase → SQL Editor → New query → Run

create table if not exists public.users (
  id text primary key,                       -- uuid anonimo generado en el navegador
  created_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now()
);

create table if not exists public.outfits (
  id uuid primary key default gen_random_uuid(),
  user_id text not null references public.users(id) on delete cascade,
  garment_url text not null,
  description text,
  created_at timestamptz not null default now()
);

create table if not exists public.tryon_jobs (
  id text primary key,                       -- uuid hex generado por el backend
  user_id text not null default 'anonymous',
  outfit_id uuid references public.outfits(id) on delete set null,
  status text not null check (status in ('queued','processing','done','error')),
  stage text not null,
  description text,
  garment_url text,
  person_url text,
  base_image_url text,
  improved_prompt text,
  final_image_url text,
  refined boolean,
  category text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.tryon_jobs add column if not exists refined boolean;
alter table public.tryon_jobs add column if not exists category text;

create index if not exists tryon_jobs_user_created_idx on public.tryon_jobs (user_id, created_at desc);
create index if not exists tryon_jobs_status_idx on public.tryon_jobs (status);

-- El backend usa la service key (bypass RLS). El navegador nunca habla con Supabase directamente.
alter table public.users enable row level security;
alter table public.outfits enable row level security;
alter table public.tryon_jobs enable row level security;

-- Limpieza de jobs antiguos (Supabase → Database → Extensions → pg_cron)
-- select cron.schedule('purge-tryon-jobs', '0 4 * * *',
--   $$ delete from public.tryon_jobs where created_at < now() - interval '30 days' $$);
