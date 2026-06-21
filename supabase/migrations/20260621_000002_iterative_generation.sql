-- Secure iterative generation, branchable versions, durable chat, and private source images.

alter table public.nc_versions
  add column if not exists spec jsonb null,
  add column if not exists spec_delta jsonb not null default '[]'::jsonb,
  add column if not exists change_summary text not null default '';

alter table public.nc_sessions
  add column if not exists expires_at timestamptz;

update public.nc_sessions
set expires_at = created_at + interval '7 days'
where expires_at is null;

alter table public.nc_sessions
  alter column expires_at set default (now() + interval '7 days'),
  alter column expires_at set not null;

create table if not exists public.nc_messages (
  id text primary key,
  project_id text not null references public.nc_projects(id) on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  attachment_ids jsonb not null default '[]'::jsonb,
  run_id text null,
  version_id text null references public.nc_versions(id) on delete set null,
  created_at timestamptz not null default now()
);

create table if not exists public.nc_generation_runs (
  id text primary key,
  project_id text not null references public.nc_projects(id) on delete cascade,
  session_id text not null references public.nc_sessions(id) on delete cascade,
  parent_version_id text null references public.nc_versions(id) on delete set null,
  idempotency_key text not null,
  message text not null,
  attachment_ids jsonb not null default '[]'::jsonb,
  profile text not null check (profile in ('fast', 'balanced', 'quality')),
  status text not null check (status in (
    'submitted', 'resolving_spec', 'awaiting_clarification', 'generating_code',
    'executing', 'publishing', 'completed', 'failed'
  )),
  draft_spec jsonb null,
  spec_delta jsonb not null default '[]'::jsonb,
  change_summary text not null default '',
  clarification_questions jsonb not null default '[]'::jsonb,
  error text null,
  version_id text null references public.nc_versions(id) on delete set null,
  telemetry jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(project_id, idempotency_key)
);

alter table public.nc_messages
  drop constraint if exists nc_messages_run_id_fkey,
  add constraint nc_messages_run_id_fkey foreign key (run_id)
    references public.nc_generation_runs(id) on delete set null;

create table if not exists public.nc_attachments (
  id text primary key,
  project_id text not null references public.nc_projects(id) on delete cascade,
  owner_session_id text not null references public.nc_sessions(id) on delete cascade,
  status text not null check (status in ('reserved', 'processing', 'ready', 'failed', 'deleted')),
  content_type text not null check (content_type in ('image/jpeg', 'image/png', 'image/webp')),
  size_bytes integer not null check (size_bytes > 0 and size_bytes <= 8388608),
  storage_key text not null unique,
  sanitized_storage_key text null unique,
  width integer null,
  height integer null,
  checksum_sha256 text null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_nc_messages_project on public.nc_messages(project_id, created_at);
create index if not exists idx_nc_runs_project on public.nc_generation_runs(project_id, created_at desc);
create index if not exists idx_nc_attachments_project on public.nc_attachments(project_id, created_at desc);
create index if not exists idx_nc_attachments_expiry on public.nc_attachments(expires_at) where status <> 'deleted';

-- Service-role API calls this RPC. The advisory lock makes count + insert atomic
-- for one session without serializing unrelated users.
create or replace function public.nc_reserve_generation_quota(
  p_session_id text,
  p_max_runs integer,
  p_window_seconds integer
)
returns table(allowed boolean, remaining integer)
language plpgsql
security definer
set search_path = public
as $$
declare
  used integer;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_session_id, 0));
  select count(*)::integer into used
  from public.nc_usage_events
  where session_id = p_session_id
    and event_type = 'generation'
    and created_at >= now() - make_interval(secs => p_window_seconds);

  if used >= p_max_runs then
    return query select false, 0;
    return;
  end if;

  insert into public.nc_usage_events(session_id, event_type)
  values (p_session_id, 'generation');
  return query select true, greatest(p_max_runs - used - 1, 0);
end;
$$;

revoke all on function public.nc_reserve_generation_quota(text, integer, integer) from public, anon, authenticated;
grant execute on function public.nc_reserve_generation_quota(text, integer, integer) to service_role;

create or replace function public.nc_reserve_attachment(
  p_id text,
  p_project_id text,
  p_owner_session_id text,
  p_content_type text,
  p_size_bytes integer,
  p_storage_key text,
  p_expires_at timestamptz,
  p_max_active integer
)
returns table(reserved boolean)
language plpgsql
security definer
set search_path = public
as $$
declare
  active_count integer;
begin
  perform pg_advisory_xact_lock(hashtextextended(p_project_id || ':attachments', 0));
  select count(*)::integer into active_count
  from public.nc_attachments
  where project_id = p_project_id and status not in ('failed', 'deleted');
  if active_count >= p_max_active then
    return query select false;
    return;
  end if;
  insert into public.nc_attachments(
    id, project_id, owner_session_id, status, content_type, size_bytes, storage_key, expires_at
  ) values (
    p_id, p_project_id, p_owner_session_id, 'reserved', p_content_type, p_size_bytes, p_storage_key, p_expires_at
  );
  return query select true;
end;
$$;

revoke all on function public.nc_reserve_attachment(text, text, text, text, integer, text, timestamptz, integer) from public, anon, authenticated;
grant execute on function public.nc_reserve_attachment(text, text, text, text, integer, text, timestamptz, integer) to service_role;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
  'naturalcad-source-images',
  'naturalcad-source-images',
  false,
  8388608,
  array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update set
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
