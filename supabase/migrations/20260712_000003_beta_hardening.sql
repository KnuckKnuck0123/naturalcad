-- Beta hardening: exclusive run-processing claims + per-IP abuse limits.

-- 1. Run claims. process_generation must hold a fresh claim to work on a run;
--    the poll-triggered recovery loop can only steal a stale claim (dead worker).
alter table public.nc_generation_runs
  add column if not exists claimed_at timestamptz null,
  add column if not exists claim_token text null;

-- 2. Per-IP sliding-window limits. Guest sessions are free to mint, so public-beta
--    abuse control must also key on client IP (Cloudflare/Cloud Run forwarded IP).
create table if not exists public.nc_ip_quota_events (
  id bigint generated always as identity primary key,
  ip_hash text not null,
  kind text not null check (kind in ('session', 'run')),
  created_at timestamptz not null default now()
);

create index if not exists idx_nc_ip_quota_events_lookup
  on public.nc_ip_quota_events(ip_hash, kind, created_at desc);

-- Same shape as nc_reserve_generation_quota: advisory lock makes count + insert
-- atomic per (ip, kind) without serializing unrelated clients.
create or replace function public.nc_reserve_ip_quota(
  p_ip_hash text,
  p_kind text,
  p_max_events integer,
  p_window_seconds integer
)
returns table(allowed boolean, remaining integer)
language plpgsql
security definer
set search_path = public
as $$
declare
  v_count integer;
begin
  perform pg_advisory_xact_lock(hashtext('nc_ip_quota:' || p_ip_hash || ':' || p_kind));
  delete from public.nc_ip_quota_events
    where ip_hash = p_ip_hash and kind = p_kind
      and created_at < now() - make_interval(secs => p_window_seconds);
  select count(*) into v_count from public.nc_ip_quota_events
    where ip_hash = p_ip_hash and kind = p_kind;
  if v_count >= p_max_events then
    return query select false, 0;
    return;
  end if;
  insert into public.nc_ip_quota_events(ip_hash, kind) values (p_ip_hash, p_kind);
  return query select true, p_max_events - v_count - 1;
end;
$$;

revoke all on function public.nc_reserve_ip_quota(text, text, integer, integer) from public;
grant execute on function public.nc_reserve_ip_quota(text, text, integer, integer) to service_role;
