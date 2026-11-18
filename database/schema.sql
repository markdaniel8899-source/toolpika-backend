-- Toolpika minimal schema. No RLS. Admin protection is at middleware level.

create table if not exists public.profiles (
  id uuid primary key,
  email text not null,
  role text not null default 'admin',
  created_at timestamptz not null default now()
);

create table if not exists public.tools (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  title text not null,
  category text not null,
  icon text,
  description text not null,
  status text not null default 'live',
  usage_count integer not null default 0,
  created_at timestamptz not null default now()
);

create table if not exists public.inbox_messages (
  id uuid primary key default gen_random_uuid(),
  type text not null check (type in ('tool_request', 'contact')),
  name text,
  email text,
  tool_name text,
  description text not null,
  status text not null default 'new',
  created_at timestamptz not null default now()
);

-- Seed tools
insert into public.tools (slug, title, category, icon, description, status) values
  ('word-counter',       'Word Counter',             'text',      'FileText',   'Count words, characters, sentences and paragraphs.', 'live'),
  ('case-converter',     'Case Converter',           'text',      'Type',       'Convert text to UPPERCASE, lowercase, Title Case.',   'live'),
  ('image-compressor',   'Image Compressor',         'image',     'Image',      'Compress JPEG and PNG in your browser.',             'live'),
  ('json-formatter',     'JSON Formatter',           'code',      'Code',       'Format, validate and minify JSON.',                  'live'),
  ('unit-converter',     'Unit Converter',           'converter', 'LayoutGrid', 'Convert length, weight, temperature.',               'live'),
  ('password-generator', 'Password Generator',       'security',  'Shield',     'Generate strong random passwords.',                  'live'),
  ('url-encoder',        'URL Encoder / Decoder',    'converter', 'Link',       'Encode or decode URLs.',                             'live'),
  ('base64-encoder',     'Base64 Encoder / Decoder', 'converter', 'Copy',       'Encode or decode Base64 strings.',                   'live')
on conflict (slug) do nothing;
