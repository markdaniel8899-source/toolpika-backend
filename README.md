# Toolpika — Autonomous Backend

FastAPI service that researches trending tool ideas, generates a complete
`ToolSpec`, runs hard QA with self-correction, publishes to Supabase, and then
fans the content out to every supported locale through Groq.

---

## Quick start

```bash
cd backend
cp .env.example .env          # fill in the keys
pip install -r requirements.txt
bash scripts/run_tests.sh
bash scripts/run_server.sh
# http://localhost:8000/docs
```

Docker (from the **repository root**, because the template lives in `/markdown`):

```bash
docker build -f backend/Dockerfile -t toolpika-backend .
docker compose -f backend/docker-compose.yml up -d
```

---

## Environment variables

| Variable | Required | Purpose |
| :--- | :---: | :--- |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | Server-side DB writes |
| `SUPABASE_ANON_KEY` | — | Optional public key |
| `TAVILY_API_KEY` | ✅ | Trending-tool research |
| `NVIDIA_NIM_API_KEY` | ✅ | Nemotron tool-spec generation |
| `GROQ_API_KEY` | ✅ | Chunked translation |
| `QSTASH_URL`, `QSTASH_TOKEN` | — | Reserved for a future hosted queue; unused today |
| `APP_ENV` | — | `production` default; set `test` to skip key validation |
| `APP_HOST`, `APP_PORT`, `LOG_LEVEL` | — | Uvicorn / logging |
| `FRONTEND_URL` | — | CORS / callbacks |
| `CRON_RESEARCH_ENABLED`, `CRON_RESEARCH_SCHEDULE` | — | Daily cron (default `0 3 * * *`) |
| `QA_MAX_RETRIES` | — | Max QA attempts (default 3) |
| `TRANSLATION_DELAY_MINUTES` | — | Publish → translate delay (default 5) |
| `TRANSLATION_CALL_DELAY_SECONDS` | — | Groq call spacing (default 1) |
| `DEFAULT_LOCALES` | — | Comma-separated locales, default `de,fr,es,it,pt-BR,ru,tr,ar,hi` |
| `TEMPLATE_PATH` | — | Override path to `UNIVERSAL_TOOL_TEMPLATE.md` |

**Deployment note:** the translation key must be set **on the backend server**,
not only on Vercel. Vercel only serves the Next.js frontend.

---

## API

| Method | Path | Purpose |
| :--- | :--- | :--- |
| `POST` | `/api/pipeline/research-and-build` | Full pipeline; optional `{"topic": "..."}` |
| `POST` | `/api/pipeline/translate` | `{"slug": "...", "locales": ["de"]}` |
| `GET` | `/api/tools` | All tools + status |
| `GET` | `/api/tools/{slug}` | Full spec + translation status |
| `POST` | `/api/tools/{slug}/retry-qa` | Re-run QA |
| `POST` | `/api/tools/{slug}/republish` | Force re-publish |
| `GET` | `/api/admin/pipeline-status` | Queue depth + last 10 runs |
| `GET` | `/api/admin/logs` | Filtered logs (`stage`, `status`, `limit`) |
| `POST` | `/api/admin/trigger-cron` | Manual daily job |
| `GET` | `/api/admin/config` | Safe config for frontend |
| `GET` | `/health` | Liveness + uptime |
| `GET` | `/ready` | Provider credential checks |

Frontend should point at `https://api.toolpika.site` via `BACKEND_API_URL`.
CORS origins are `toolpika.vercel.app`, `localhost:3000`, `toolpika.site`.

---

## Database

Apply `backend/database/schema.sql` first, then `backend/database/001_pipeline.sql`
(or run `python scripts/migrate.py` and paste the output into the Supabase SQL
editor). New tables: `tool_specs`, `content_translations`, `pipeline_runs`.

Idempotency: `tool_specs.slug` is the primary key and `source_hash` is stored, so
running the pipeline twice on the same slug upserts instead of duplicating.
Translations are keyed by `(locale, slug, chunk)`.

---

## Deployment (one paragraph)

Provision a small Linux VM with Docker and Caddy, copy the repository to
`/opt/toolpika`, create `/opt/toolpika/backend/.env` from `.env.example` with
real Supabase, Tavily, NVIDIA NIM and Groq keys, build the image from the repo
root (`docker build -f backend/Dockerfile .`), apply both SQL migrations in
Supabase, then run the container behind Caddy using the included `Caddyfile`
pointing `api.toolpika.site` at `localhost:8000`. Set a systemd unit (or compose
restart policy) to keep it alive, add `BACKEND_API_URL=https://api.toolpika.site`
to the Next.js environment, and verify with `curl https://api.toolpika.site/ready`.
Cron runs at 03:00 UTC by default and the T+5-minute translation job is queued
in-process, so a restart before it fires will drop that single job — use QStash
or a DB-backed queue if that must survive restarts.

---

## Deliberate deviations from the brief (and why)

1. **`UNIVERSAL_TOOL_TEMPLATE.md` did not exist** in `/markdown`. It was
   reconstructed from the brief's field and rule list and is now the canonical
   file. Replace it with the original if you have one; the loader reads it at
   runtime, so no code change is needed.
2. **`upstash-qstash==2.3.0` does not exist on PyPI.** Delayed jobs are
   implemented with APScheduler; `QSTASH_*` variables are kept as optional
   placeholders for a future hosted queue.
3. **Locale list follows the frontend**, not the brief's example list: the site
   supports `de, fr, es, it, pt-BR, ru, tr, ar, hi` (plus `en`). The brief listed
   `pt, nl, pl` and omitted `ru`; changing that would require frontend routing
   changes. Override with `DEFAULT_LOCALES`.
4. **Example verification** uses Python reference functions for common tools
   (`word-counter`, `case-converter`, `base64-*`, `json-formatter`, `url-*`).
   Unknown tools get a structural check: the TypeScript implementation cannot
   be executed from Python.
5. **No auth on admin endpoints.** Put Caddy basic auth or a gateway in front of
   `/api/admin/*` and `/api/pipeline/*` before public deployment.
6. **Reading-level warning** is a sentence-length heuristic, not a full
   Flesch–Kincaid implementation.

---

## Tests

`bash scripts/run_tests.sh` — 49 tests, all offline with mocked providers:
research, generator, QA validator, translator, endpoints and full integration.
