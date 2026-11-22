-- Upgrade the research inbox into an AI strategy engine.
-- Apply after database/003_cleanup_and_ideas.sql.

alter table public.tool_ideas
  add column if not exists report_details jsonb,
  add column if not exists search_volume text default 'N/A',
  add column if not exists competition text default 'N/A';

comment on column public.tool_ideas.report_details is
  'Extra scouted stats: search_volume, competition, target_audience, sources.';

comment on column public.tool_ideas.search_volume is
  'Estimated demand signal, e.g. High, Medium, Low or N/A.';

comment on column public.tool_ideas.competition is
  'Estimated competition level, e.g. Low, Medium, High or N/A.';
