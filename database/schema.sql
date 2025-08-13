-- Schema for JobTrackAI
-- Run this in Supabase SQL Editor

-- Extensions
create extension if not exists pgcrypto;

-- Users
create table if not exists users (
    id uuid primary key default gen_random_uuid(),
    phone_e164 text unique not null,
    display_name text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_users_created_at on users (created_at desc);

-- Conversations
create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    title text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_message_at timestamptz null
);

create index if not exists idx_conversations_user_recency on conversations (user_id, last_message_at desc nulls last, updated_at desc);

-- Messages
create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    role text not null check (role in ('user','assistant')),
    content text not null,
    tool_calls jsonb null,
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conv_created on messages (conversation_id, created_at desc, id desc);

-- Jobs
create table if not exists jobs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    job_title text not null,
    company_name text not null,
    job_link text null,
    job_description text null,
    status text not null default 'applied',
    date_added timestamptz not null default now(),
    last_updated timestamptz not null default now()
);

create index if not exists idx_jobs_user_date on jobs (user_id, date_added desc);
create index if not exists idx_jobs_user_company on jobs (user_id, company_name);
create index if not exists idx_jobs_user_title on jobs (user_id, job_title);

-- Updated_at auto-maintenance
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_users_updated on users;
create trigger trg_users_updated before update on users
for each row execute function set_updated_at();

drop trigger if exists trg_conversations_updated on conversations;
create trigger trg_conversations_updated before update on conversations
for each row execute function set_updated_at();

