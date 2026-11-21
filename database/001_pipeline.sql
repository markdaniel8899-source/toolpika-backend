-- Toolpika autonomous pipeline tables.
-- Apply in the Supabase SQL editor after backend/database/schema.sql.

create table if not exists public.tool_specs (
  slug text primary key,
  spec jsonb not null,
  status text not null default 'published',
  translation_status text not null default 'pending',
  source_hash text,
  tier integer default 1,
  category text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.content_translations (
  locale text not null,
  slug text not null references public.tool_specs(slug) on delete cascade,
  chunk text not null,
  content jsonb not null,
  status text not null default 'published',
  updated_at timestamptz not null default now(),
  primary key (locale, slug, chunk)
);

create table if not exists public.pipeline_runs (
  id bigint generated always as identity primary key,
  stage text,
  status text,
  details jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_content_translations_slug
  on public.content_translations(slug);
create index if not exists idx_pipeline_runs_created
  on public.pipeline_runs(created_at desc);
