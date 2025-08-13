-- Messages table
-- Run in Supabase SQL editor

create extension if not exists pgcrypto;

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    user_id uuid not null references users(id) on delete cascade,
    role text not null check (role in ('user','assistant')),
    content text not null,
    tool_calls jsonb null,
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conv_created
  on messages (conversation_id, created_at desc, id desc);


