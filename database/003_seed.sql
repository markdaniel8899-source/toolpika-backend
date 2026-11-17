-- =============================================================================
-- Toolpika — 003_seed.sql
-- Seed categories and the live tool registry so the admin dashboard and the
-- database agree with frontend/src/lib/tools/registry.ts.
--
-- Re-runnable: uses ON CONFLICT DO UPDATE.
-- =============================================================================

insert into public.categories (slug, label, icon, sort_order) values
  ('text',      'Text',       'FileText',   1),
  ('image',     'Images',     'Image',      2),
  ('file',      'Files',      'FileText',   3),
  ('code',      'Code',       'Code',       4),
  ('converter', 'Converters', 'LayoutGrid', 5),
  ('security',  'Security',   'Shield',     6),
  ('calculator','Calculators','LayoutGrid', 7)
on conflict (slug) do update
  set label = excluded.label,
      icon = excluded.icon,
      sort_order = excluded.sort_order;

insert into public.tools (slug, title, category, icon, description, status) values
  ('word-counter',        'Word Counter',            'text',      'FileText',   'Count words, characters, sentences and paragraphs in your text.',          'live'),
  ('case-converter',      'Case Converter',          'text',      'Type',       'Convert text to UPPERCASE, lowercase, Title Case or camelCase.',        'live'),
  ('image-compressor',    'Image Compressor',        'image',     'Image',      'Compress JPEG and PNG images locally in your browser.',                   'live'),
  ('json-formatter',      'JSON Formatter',          'code',      'Code',       'Format, validate and minify JSON in your browser.',                        'live'),
  ('unit-converter',      'Unit Converter',          'converter', 'LayoutGrid', 'Convert length, weight, temperature and more.',                            'live'),
  ('password-generator',  'Password Generator',      'security',  'Shield',     'Generate strong, random passwords locally.',                               'live'),
  ('url-encoder',         'URL Encoder / Decoder',   'converter', 'Link',       'Encode or decode URLs and query strings.',                                 'live'),
  ('base64-encoder',      'Base64 Encoder / Decoder','converter', 'Copy',       'Encode or decode Base64 strings.',                                         'live')
on conflict (slug) do update
  set title = excluded.title,
      category = excluded.category,
      icon = excluded.icon,
      description = excluded.description,
      status = excluded.status;
