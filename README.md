# Toolpika — AI Research Scout

A deliberately small FastAPI service. It scouts Reddit, Quora and Product Hunt
for repeated tool requests, asks Nemotron for 3-5 micro-tool ideas, and stores
them in `tool_ideas` for manual admin review.

**It does not generate tool code, ToolSpecs, QA results or translations.**

---

## Quick start

```bash
cd backend
cp .env.example .env          # fill in the keys
pip install -r requirements.txt
python -m pytest -q
bash scripts/run_server.sh    # http://localhost:8000/docs
```

Apply `database/003_cleanup_and_ideas.sql` in the Supabase SQL editor first.
It drops the abandoned generation tables and creates the `tool_ideas` inbox.

---

## Environment

| Variable | Required | Purpose |
| :--- | :---: | :--- |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Server-side DB access |
| `TAVILY_API_KEY` | ✅ | Web search |
| `NVIDIA_NIM_API_KEY` | ✅ | Idea analysis |
| `CRON_RESEARCH_ENABLED`, `CRON_RESEARCH_SCHEDULE` | — | Daily job (default `0 3 * * *` UTC) |
| `APP_ENV`, `APP_HOST`, `APP_PORT`, `LOG_LEVEL` | — | Runtime |

---

## API

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `GET` | `/health`, `/ready` | Liveness / provider config |
| `POST` | `/api/pipeline/research` | Run the scout now |
| `GET` | `/api/admin/ideas` | All ideas, newest first |
| `PATCH` | `/api/admin/ideas/{id}` | `{"status": "new|reviewed|rejected|building"}` |

The admin UI lives at `/admin/ideas` in the frontend repo.

---

## Daily job

`app/pipelines/cron_scheduler.py` registers one APScheduler cron job at 03:00
UTC that calls `research_scout.run_research_scout()`. There are no build,
QA, retry or translation jobs.
