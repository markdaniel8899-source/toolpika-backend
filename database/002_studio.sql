-- Tool Studio tables: chat sessions, messages and generated tool drafts.
-- Apply in the Supabase SQL editor after backend/database/001_pipeline.sql.

create table if not exists public.studio_sessions (
  id uuid primary key,
  title text not null default 'Untitled tool',
  idea text,
  source_url text,
  stage text not null default 'intake',
  status text not null default 'active',
  context jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.studio_messages (
  id uuid primary key,
  session_id uuid not null references public.studio_sessions(id) on delete cascade,
  role text not null,
  content text not null,
  artifacts jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.tool_drafts (
  id uuid primary key,
  session_id uuid not null references public.studio_sessions(id) on delete cascade,
  slug text not null,
  blueprint jsonb not null default '{}'::jsonb,
  spec jsonb,
  code_files jsonb not null default '[]'::jsonb,
  qa jsonb not null default '{}'::jsonb,
  status text not null default 'draft',
  preview_url text,
  pr_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_studio_messages_session
  on public.studio_messages(session_id, created_at);
create index if not exists idx_tool_drafts_session
  on public.tool_drafts(session_id, updated_at desc);
create index if not exists idx_studio_sessions_updated
  on public.studio_sessions(updated_at desc);

-- Row level security: the backend uses the service role; admin UI access goes
-- through the backend API, so direct anonymous access is not required.
alter table public.studio_sessions enable row level security;
alter table public.studio_messages enable row level security;
alter table public.tool_drafts enable row level security;
