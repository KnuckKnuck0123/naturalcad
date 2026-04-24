-- NaturalCAD domain app v1 schema
-- Apply with: supabase db push

create extension if not exists pgcrypto;

create table if not exists public.nc_sessions (
  id text primary key,
  actor_type text not null check (actor_type in ('guest','user')),
  user_id uuid null,
  created_at timestamptz not null default now()
);

create table if not exists public.nc_projects (
  id text primary key,
  owner_session_id text not null references public.nc_sessions(id) on delete cascade,
  title text not null,
  mode text not null check (mode in ('part','assembly','sketch')),
  output_type text not null check (output_type in ('3d_solid','surface','2d_vector','1d_path')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.nc_versions (
  id text primary key,
  project_id text not null references public.nc_projects(id) on delete cascade,
  parent_version_id text null references public.nc_versions(id) on delete set null,
  prompt text not null,
  profile text not null check (profile in ('fast','balanced','quality')),
  model text not null,
  status text not null check (status in ('completed','failed')),
  error text null,
  artifacts jsonb not null default '{}'::jsonb,
  generated_code text not null default '',
  parameters jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.nc_usage_events (
  id uuid primary key default gen_random_uuid(),
  session_id text not null references public.nc_sessions(id) on delete cascade,
  project_id text null references public.nc_projects(id) on delete set null,
  version_id text null references public.nc_versions(id) on delete set null,
  event_type text not null,
  profile text null,
  cost_cents integer null,
  tokens_input integer null,
  tokens_output integer null,
  created_at timestamptz not null default now()
);

create index if not exists idx_nc_projects_owner on public.nc_projects(owner_session_id);
create index if not exists idx_nc_versions_project on public.nc_versions(project_id, created_at desc);
create index if not exists idx_nc_usage_session on public.nc_usage_events(session_id, created_at desc);
