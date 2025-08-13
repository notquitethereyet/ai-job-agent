-- Conversations table
-- Run in Supabase SQL editor

create extension if not exists pgcrypto;

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null references users(id) on delete cascade,
    title text null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    last_message_at timestamptz null
);

create index if not exists idx_conversations_user_recency
  on conversations (user_id, last_message_at desc nulls last, updated_at desc);

-- Maintain updated_at automatically
create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_conversations_updated on conversations;
create trigger trg_conversations_updated
before update on conversations
for each row execute function set_updated_at();


