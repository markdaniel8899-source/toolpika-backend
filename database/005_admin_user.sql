-- =============================================================================
-- Toolpika — 005_admin_user.sql
-- Admin profile for the Supabase Auth user.
--
-- IMPORTANT — DO THIS FIRST IN THE SUPABASE DASHBOARD:
--   Authentication → Users → Add user → "Create user"
--   Email:    hafizmzain786@gmail.com
--   Password: Toolpika@2026
--   (Tick "Auto Confirm User" so the account can sign in immediately.)
--
-- After the user is created, copy its UUID from the Users list (the "UID"
-- column) and paste it in place of the placeholder below.
-- Then run this file in the SQL Editor. The password is NEVER stored here —
-- it lives only in Supabase Auth, hashed by Supabase.
-- =============================================================================

-- 👉 PASTE THE UUID FROM SUPABASE DASHBOARD → AUTHENTICATION → USERS HERE 👇
--    Replace the entire string 'REPLACE_WITH_AUTH_USER_UUID' including quotes.
--    Example: '9c3f2a1e-7b44-4d0f-9a2c-1f8e6b5d4a3c'

insert into public.profiles (id, email, role)
values (
  'REPLACE_WITH_AUTH_USER_UUID',
  'hafizmzain786@gmail.com',
  'admin'
)
on conflict (id) do update
  set email = excluded.email,
      role = 'admin';
