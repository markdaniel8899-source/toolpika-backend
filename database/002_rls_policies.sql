-- =============================================================================
-- Toolpika — 002_rls_policies.sql
-- Row-Level Security for every public table.
--
-- Reading rules:
--   * anon        -> may read only published/live public content
--   * authenticated -> may read live content and insert a tool request
--   * admin       -> full access (checked via private.is_admin)
--
-- The admin check NEVER queries public.profiles from inside a profiles
-- policy. It goes through the SECURITY DEFINER helper in 001, which is what
-- keeps RLS from recursing.
-- =============================================================================

alter table public.profiles enable row level security;
alter table public.categories enable row level security;
alter table public.tools enable row level security;
alter table public.tool_requests enable row level security;
alter table public.posts enable row level security;
alter table public.post_views_daily enable row level security;
alter table public.site_settings enable row level security;
alter table public.translations enable row level security;

-- -----------------------------------------------------------------------------
-- profiles
-- -----------------------------------------------------------------------------
drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own
  on public.profiles
  for select
  to authenticated
  using ((select auth.uid()) = id);

drop policy if exists profiles_select_admin on public.profiles;
create policy profiles_select_admin
  on public.profiles
  for select
  to authenticated
  using ((select private.is_admin()));

drop policy if exists profiles_insert_self on public.profiles;
create policy profiles_insert_self
  on public.profiles
  for insert
  to authenticated
  with check ((select auth.uid()) = id);

drop policy if exists profiles_update_admin on public.profiles;
create policy profiles_update_admin
  on public.profiles
  for update
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

drop policy if exists profiles_delete_admin on public.profiles;
create policy profiles_delete_admin
  on public.profiles
  for delete
  to authenticated
  using ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- categories — public read, admin write
-- -----------------------------------------------------------------------------
drop policy if exists categories_select_public on public.categories;
create policy categories_select_public
  on public.categories
  for select
  to anon, authenticated
  using (true);

drop policy if exists categories_admin_all on public.categories;
create policy categories_admin_all
  on public.categories
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- tools — live tools are public, drafts are admin-only
-- -----------------------------------------------------------------------------
drop policy if exists tools_select_live on public.tools;
create policy tools_select_live
  on public.tools
  for select
  to anon, authenticated
  using (status = 'live');

drop policy if exists tools_select_admin on public.tools;
create policy tools_select_admin
  on public.tools
  for select
  to authenticated
  using ((select private.is_admin()));

drop policy if exists tools_admin_write on public.tools;
create policy tools_admin_write
  on public.tools
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- tool_requests — anyone may submit, only admin may read/manage
-- -----------------------------------------------------------------------------
drop policy if exists tool_requests_insert_public on public.tool_requests;
create policy tool_requests_insert_public
  on public.tool_requests
  for insert
  to anon, authenticated
  with check (true);

drop policy if exists tool_requests_admin_all on public.tool_requests;
create policy tool_requests_admin_all
  on public.tool_requests
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- posts — published posts are public
-- -----------------------------------------------------------------------------
drop policy if exists posts_select_published on public.posts;
create policy posts_select_published
  on public.posts
  for select
  to anon, authenticated
  using (status = 'published');

drop policy if exists posts_admin_all on public.posts;
create policy posts_admin_all
  on public.posts
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- post_views_daily — counters are public, only admin may write
-- -----------------------------------------------------------------------------
drop policy if exists post_views_daily_select_public on public.post_views_daily;
create policy post_views_daily_select_public
  on public.post_views_daily
  for select
  to anon, authenticated
  using (true);

drop policy if exists post_views_daily_admin_all on public.post_views_daily;
create policy post_views_daily_admin_all
  on public.post_views_daily
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- site_settings — readable and writable by admins only
-- -----------------------------------------------------------------------------
drop policy if exists site_settings_admin_all on public.site_settings;
create policy site_settings_admin_all
  on public.site_settings
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

-- -----------------------------------------------------------------------------
-- translations — public read for live resources, admin write
-- -----------------------------------------------------------------------------
drop policy if exists translations_select_public on public.translations;
create policy translations_select_public
  on public.translations
  for select
  to anon, authenticated
  using (true);

drop policy if exists translations_admin_all on public.translations;
create policy translations_admin_all
  on public.translations
  for all
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));
