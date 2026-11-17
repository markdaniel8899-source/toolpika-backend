-- =============================================================================
-- Toolpika — 001_initial_schema.sql
-- Core schema for the admin dashboard, tool registry, requests, blog and i18n.
--
-- Design rules (see .agents/design-constitution.md and
-- .agents/README.md §6):
--   * RLS policies never recurse. The admin check lives in a SECURITY
--     DEFINER helper in the private schema, not inline in the policy.
--   * Every RLS-checked column is indexed.
--   * auth.uid() is wrapped in (select ...) so it is evaluated once per query.
--   * NO table stores user files or tool file contents. Ever.
-- =============================================================================

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- private schema — internal helpers, not exposed through the API
-- -----------------------------------------------------------------------------
create schema if not exists private;

-- -----------------------------------------------------------------------------
-- Profiles
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text not null,
  role text not null default 'user' check (role in ('user', 'admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.profiles is
  'Admin accounts. role = admin grants access to the /admin dashboard.';

create index if not exists profiles_role_idx
  on public.profiles (role)
  where role = 'admin';

-- SECURITY DEFINER helper: avoids the RLS recursion that a direct
-- "select from profiles" inside a profiles policy would cause.
--
-- The function reads auth.uid() itself, so a caller cannot ask about another
-- user's role. It lives in the private schema, which the Data API does not
-- expose.
create or replace function private.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.profiles p
    where p.id = (select auth.uid())
      and p.role = 'admin'
  );
$$;

revoke execute on function private.is_admin() from public, anon;
grant execute on function private.is_admin() to authenticated, service_role;

-- -----------------------------------------------------------------------------
-- Profile bootstrap — every auth user gets a profile row on sign-up
-- -----------------------------------------------------------------------------
create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  insert into public.profiles (id, email)
  values (new.id, coalesce(new.email, ''))
  on conflict (id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- -----------------------------------------------------------------------------
-- Categories
-- -----------------------------------------------------------------------------
create table if not exists public.categories (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  label text not null,
  icon text,
  sort_order integer not null default 0,
  created_at timestamptz not null default now()
);

comment on table public.categories is
  'Tool categories. Mirrors the typed registry in frontend/src/lib/tools/registry.ts.';

create index if not exists categories_sort_order_idx
  on public.categories (sort_order);

-- -----------------------------------------------------------------------------
-- Tools
-- -----------------------------------------------------------------------------
create table if not exists public.tools (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  category text not null references public.categories (slug) on update cascade,
  icon text,
  description text not null,
  status text not null default 'draft' check (status in ('draft', 'live', 'hidden')),
  usage_count integer not null default 0 check (usage_count >= 0),
  seo_title text,
  seo_description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.tools is
  'Tool metadata only. No file contents, no uploads, no processing artifacts.';

comment on column public.tools.usage_count is
  'Real run count. Never seeded with invented numbers.';

create index if not exists tools_status_idx on public.tools (status);
create index if not exists tools_category_idx on public.tools (category);
create index if not exists tools_usage_count_idx
  on public.tools (usage_count desc)
  where status = 'live';

-- -----------------------------------------------------------------------------
-- Tool requests
-- -----------------------------------------------------------------------------
create table if not exists public.tool_requests (
  id uuid primary key default gen_random_uuid(),
  tool_name text not null,
  description text not null,
  email text,
  status text not null default 'new' check (status in ('new', 'building', 'launched')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.tool_requests is
  'Submissions from the /request page. Free text only — no files.';

create index if not exists tool_requests_status_idx
  on public.tool_requests (status, created_at desc);

-- -----------------------------------------------------------------------------
-- Blog posts
-- -----------------------------------------------------------------------------
create table if not exists public.posts (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  content text not null default '',
  status text not null default 'draft' check (status in ('draft', 'published')),
  seo_title text,
  seo_description text,
  seo_score integer check (seo_score between 0 and 100),
  views integer not null default 0 check (views >= 0),
  published_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

comment on table public.posts is
  'Long-form guides and articles. Markdown or rich text.';

create index if not exists posts_status_published_idx
  on public.posts (published_at desc)
  where status = 'published';

-- -----------------------------------------------------------------------------
-- Daily post views — aggregated counters, no visitor data
-- -----------------------------------------------------------------------------
create table if not exists public.post_views_daily (
  post_id uuid not null references public.posts (id) on delete cascade,
  day date not null,
  views integer not null default 0 check (views >= 0),
  primary key (post_id, day)
);

comment on table public.post_views_daily is
  'Per-day view counters for published posts. Holds no visitor identifier, no IP and no user agent.';

create index if not exists post_views_daily_day_idx
  on public.post_views_daily (day);

-- -----------------------------------------------------------------------------
-- Site settings
-- -----------------------------------------------------------------------------
create table if not exists public.site_settings (
  key text primary key,
  value text not null default '',
  updated_at timestamptz not null default now()
);

comment on table public.site_settings is
  'Editable site details from the admin settings page. API keys are never stored here — they live in the deployment environment.';

-- -----------------------------------------------------------------------------
-- Translations
-- -----------------------------------------------------------------------------
create table if not exists public.translations (
  id uuid primary key default gen_random_uuid(),
  resource_type text not null check (resource_type in ('tool', 'post', 'category', 'ui')),
  resource_id uuid not null,
  locale text not null,
  translated_content jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (resource_type, resource_id, locale)
);

comment on table public.translations is
  'Groq-generated translations for dynamic content. UI strings live in frontend/messages/*.json.';

create index if not exists translations_resource_idx
  on public.translations (resource_type, resource_id);
create index if not exists translations_locale_idx
  on public.translations (locale);
create index if not exists translations_content_gin_idx
  on public.translations using gin (translated_content);

-- -----------------------------------------------------------------------------
-- updated_at triggers
-- -----------------------------------------------------------------------------
create or replace function private.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function private.set_updated_at();

drop trigger if exists tools_set_updated_at on public.tools;
create trigger tools_set_updated_at
  before update on public.tools
  for each row execute function private.set_updated_at();

drop trigger if exists tool_requests_set_updated_at on public.tool_requests;
create trigger tool_requests_set_updated_at
  before update on public.tool_requests
  for each row execute function private.set_updated_at();

drop trigger if exists posts_set_updated_at on public.posts;
create trigger posts_set_updated_at
  before update on public.posts
  for each row execute function private.set_updated_at();

drop trigger if exists site_settings_set_updated_at on public.site_settings;
create trigger site_settings_set_updated_at
  before update on public.site_settings
  for each row execute function private.set_updated_at();

drop trigger if exists translations_set_updated_at on public.translations;
create trigger translations_set_updated_at
  before update on public.translations
  for each row execute function private.set_updated_at();
