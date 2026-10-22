# SkillForge AI — Deployment Guide

`docker compose up` covers local development. This document covers running the same image somewhere production-like, and one concrete path to a free/cheap public demo instance.

## 1. What the app needs, regardless of platform

- A container built from `docker/Dockerfile`, listening on port 8000.
- A PostgreSQL 16 database, reachable via `DATABASE_URL` (async driver: `postgresql+asyncpg://...`).
- A Redis instance, reachable via `REDIS_URL`.
- Migrations applied before the app serves traffic: `alembic upgrade head`.
- Environment variables (see `.env.example` for the full list; the ones that actually matter in production):

| Variable | Notes |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@host:5432/dbname` |
| `REDIS_URL` | `redis://host:6379/0` |
| `JWT_SECRET_KEY` | Generate a real one - `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Never reuse the `.env.example` placeholder. |
| `CORS_ORIGINS` | JSON array of allowed frontend origins, e.g. `["https://your-frontend.example"]`. Never `["*"]` outside local dev. |
| `AI_PROVIDER` | `fake` (default, no key needed), `anthropic`, or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Only needed if `AI_PROVIDER` uses that provider |

Migrations don't run automatically on container start (deliberately - auto-migrating on boot is convenient until two instances start at once and race each other). Run them as a separate step: `alembic upgrade head`, then start the app.

## 2. Deploying to Render (free/cheap public demo)

Render was picked here because it hosts a Docker web service, managed Postgres, and managed Redis (called "Key Value" in Render's current docs) all in one place, with a Blueprint file so the whole stack comes up from one `render.yaml` instead of clicking through three separate dashboards.

> Render's exact free-tier limits and dashboard change over time (e.g. free Postgres instances have historically expired after a set number of days unless upgraded) - check [render.com/pricing](https://render.com/pricing) before relying on this for anything long-lived. This guide gets you a working URL to link from the README; treat it as a demo, not production hosting.

### Steps

1. In the Render dashboard: **New > Blueprint**, connect the GitHub repo, branch `main`. Render reads [`render.yaml`](../render.yaml) from the repo root and provisions the web service, Postgres, and Key Value together.
2. Nothing has to be typed in: `JWT_SECRET_KEY` uses `generateValue: true`, so Render creates a random secret, and `AI_PROVIDER` is `fake`, so no API key is needed.
3. Wait for the first deploy, then open the service URL Render shows (for this project: https://skillforge-ai-t78b.onrender.com), or `/docs` for the API. If the name `skillforge-ai` is taken Render appends random characters, so copy the real address and put it in `CORS_ORIGINS`.

### What the Blueprint does, and why

- **Database URL.** Render hands out `postgresql://...`. The app needs the async driver, so `Settings` rewrites `postgres://` and `postgresql://` to `postgresql+asyncpg://` (`app/core/config.py`, tested in `tests/unit/test_config.py`).
- **Migrations and startup.** The free plan has no Shell and no pre-deploy command, so `dockerCommand` runs [`docker/start.sh`](../docker/start.sh), which applies `alembic upgrade head` and then starts uvicorn. A script is used because Render did not run an inline `sh -c "a && b"` command correctly (it looked for one program named after the whole string). The free plan runs exactly one instance, so the race described in section 1 cannot happen here. On a paid plan with several instances, move the migration to `preDeployCommand`.
- **Port.** Render sets `PORT`; `start.sh` binds to it and falls back to 8000.
- **Client IPs behind the proxy.** The rate limiter keys on `request.client.host`. Behind Render's proxy that is the proxy's address, so every visitor would share one "5 logins per minute" bucket. `--proxy-headers --forwarded-allow-ips='*'` makes uvicorn take the address from `X-Forwarded-For`. The trade-off: a client can spoof that header to dodge the limit. Acceptable for a demo; a real deployment should trust only the proxy's address range.
- **CORS.** The pages are served by the same app, so they are same-origin. `CORS_ORIGINS` lists the service URL only to keep the setting explicit.

### Free-plan limits

- The web service sleeps after 15 minutes without traffic; the first request after that takes about a minute.
- Free Postgres expires 30 days after creation, with 14 more days to upgrade before it is deleted.
- Free Key Value does not persist data across restarts. Only caches (dashboard stats, AI responses) and rate-limit counters live there, so a restart loses nothing important.

Check [render.com/pricing](https://render.com/pricing) for the current numbers; they change over time.

The live demo is at https://skillforge-ai-t78b.onrender.com (API docs at `/docs`). It runs on the free plan, so the first request after a quiet spell takes about a minute.

## 3. Deploying elsewhere

The container itself (`docker/Dockerfile`) is standard and portable - the same image runs on Railway, Fly.io, a plain VPS with `docker compose`, or a Kubernetes cluster. What changes per platform is only how you provide `DATABASE_URL`/`REDIS_URL` and run the migration step once before traffic hits the new instance. If you deploy elsewhere, the table in section 1 is the complete list of what the app needs to know about.

## 4. Smoke-testing a deployment

Once something is live, this should all succeed against the real URL:

```bash
BASE_URL=https://your-deployment.example python scripts/load_test.py --base-url "$BASE_URL" --concurrency 2 --requests-per-worker 3
```

If that runs clean, registration, login, and the full interview loop are working against the real database and Redis instance, not just locally.
