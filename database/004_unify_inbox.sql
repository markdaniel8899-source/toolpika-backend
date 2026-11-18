-- =============================================================================
-- Toolpika — 004_unify_inbox.sql
-- Unify "Request a Tool" and "Contact Us" into a single admin inbox.
--
-- Run this ONCE on an existing Supabase project.
-- Fresh installs already get inbox_messages from 001_initial_schema.sql, so
-- every statement below is idempotent.
-- No data is deleted: rows are copied first, and the legacy table is dropped
-- only after the copy is verified.
-- =============================================================================

create table if not exists public.inbox_messages (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('tool_request', 'contact')),
  name text,
  email text,
  tool_name text,
  description text not null,
  status text not null default 'new'
    check (status in ('new', 'in_progress', 'resolved', 'rejected')),
  created_at timestamptz not null default now()
);

create index if not exists idx_inbox_type on public.inbox_messages (type);
create index if not exists idx_inbox_status on public.inbox_messages (status);
create index if not exists idx_inbox_created
  on public.inbox_messages (created_at desc);

-- -----------------------------------------------------------------------------
-- Copy legacy tool_requests rows into the unified inbox.
-- Old statuses map to the new vocabulary:
--   new      -> new
--   building -> in_progress
--   launched -> resolved
-- -----------------------------------------------------------------------------
do $$
begin
  if to_regclass('public.tool_requests') is not null then
    insert into public.inbox_messages
      (type, email, tool_name, description, status, created_at)
    select
      'tool_request',
      tr.email,
      tr.tool_name,
      tr.description,
      case tr.status
        when 'building' then 'in_progress'
        when 'launched' then 'resolved'
        else 'new'
      end,
      tr.created_at
    from public.tool_requests as tr
    where not exists (
      select 1
      from public.inbox_messages as im
      where im.type = 'tool_request'
        and im.tool_name = tr.tool_name
        and im.created_at = tr.created_at
    );

    -- Verify the copy before removing the legacy table.
    if (select count(*) from public.tool_requests)
       <= (select count(*) from public.inbox_messages where type = 'tool_request') then
      drop table public.tool_requests;
    else
      raise notice
        'tool_requests kept: copy verification failed. Investigate before dropping.';
    end if;
  end if;
end $$;

-- -----------------------------------------------------------------------------
-- RLS: public insert, admin-only read/update/delete.
-- Uses private.is_admin() (SECURITY DEFINER) so profiles RLS cannot recurse.
-- -----------------------------------------------------------------------------
alter table public.inbox_messages enable row level security;

drop policy if exists inbox_public_insert on public.inbox_messages;
create policy inbox_public_insert
  on public.inbox_messages
  for insert
  to anon, authenticated
  with check (true);

drop policy if exists inbox_admin_select on public.inbox_messages;
create policy inbox_admin_select
  on public.inbox_messages
  for select
  to authenticated
  using ((select private.is_admin()));

drop policy if exists inbox_admin_update on public.inbox_messages;
create policy inbox_admin_update
  on public.inbox_messages
  for update
  to authenticated
  using ((select private.is_admin()))
  with check ((select private.is_admin()));

drop policy if exists inbox_admin_delete on public.inbox_messages;
create policy inbox_admin_delete
  on public.inbox_messages
  for delete
  to authenticated
  using ((select private.is_admin()));
