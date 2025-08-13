-- Jobs table
-- Run in Supabase SQL editor

create extension if not exists pgcrypto;

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


