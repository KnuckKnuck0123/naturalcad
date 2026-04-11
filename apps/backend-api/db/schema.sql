-- NaturalCAD Backend v0 schema
-- Target: Supabase Postgres

create extension if not exists pgcrypto;

create table if not exists jobs (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    status text not null check (status in ('submitted', 'validated', 'queued', 'running', 'completed', 'failed')),
    prompt text not null,
    normalized_prompt text,
    mode text not null,
    output_type text not null,
    client_session_id text,
    prompt_hash text,
    spec_json jsonb,
    error_text text,
    model_info_json jsonb,
    notes_json jsonb not null default '[]'::jsonb
);

create index if not exists idx_jobs_status on jobs (status);
create index if not exists idx_jobs_created_at on jobs (created_at desc);
create index if not exists idx_jobs_prompt_hash on jobs (prompt_hash);

create table if not exists artifacts (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    job_id uuid not null references jobs(id) on delete cascade,
    kind text not null check (kind in ('stl', 'step', 'preview', 'log')),
    storage_key text not null,
    size_bytes bigint,
    expires_at timestamptz
);

create index if not exists idx_artifacts_job_id on artifacts (job_id);
create index if not exists idx_artifacts_kind on artifacts (kind);

create table if not exists audit_events (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    job_id uuid references jobs(id) on delete cascade,
    event_type text not null,
    details_json jsonb not null default '{}'::jsonb
);

create index if not exists idx_audit_events_job_id on audit_events (job_id);
create index if not exists idx_audit_events_event_type on audit_events (event_type);

create table if not exists rate_limits (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    key text not null,
    window_start timestamptz not null,
    request_count integer not null default 0
);

create index if not exists idx_rate_limits_key_window on rate_limits (key, window_start desc);
