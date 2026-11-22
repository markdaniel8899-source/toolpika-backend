-- Remove the abandoned autonomous tool-generation / Tool Studio pipeline.
-- Apply in the Supabase SQL editor after the existing schema.sql.
--
-- Keep: tools, profiles, inbox_messages, posts, post_views, site_settings.
-- Drop: generated specs, translations, pipeline logs and studio chat state.

drop table if exists public.studio_messages cascade;
drop table if exists public.tool_drafts cascade;
drop table if exists public.studio_sessions cascade;
drop table if exists public.content_translations cascade;
drop table if exists public.pipeline_runs cascade;
drop table if exists public.tool_specs cascade;

-- The new, deliberately tiny research inbox.
create table if not exists public.tool_ideas (
  id uuid default gen_random_uuid() primary key,
  tool_name text not null,
  category text not null,
  why_trending text not null,
  short_description text not null,
  estimated_difficulty text default 'Medium',
  status text default 'new',
  created_at timestamptz default now(),
  constraint tool_ideas_difficulty_check
    check (estimated_difficulty in ('Easy', 'Medium', 'Hard')),
  constraint tool_ideas_status_check
    check (status in ('new', 'reviewed', 'rejected', 'building'))
);

create index if not exists idx_tool_ideas_created_at
  on public.tool_ideas(created_at desc);

alter table public.tool_ideas enable row level security;

comment on table public.tool_ideas is
  'AI-scouted tool ideas waiting for manual admin review. No generated code or specs.';
