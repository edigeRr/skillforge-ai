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

1. Push this repo to GitHub (Render deploys from a Git repo).
2. In the Render dashboard: **New > Blueprint**, point it at the repo. Render reads `render.yaml` (below) and provisions the web service, database, and Redis together.
3. Render will prompt for the secret env vars marked `sync: false` in the blueprint (`JWT_SECRET_KEY`, and `ANTHROPIC_API_KEY`/`OPENAI_API_KEY` if you're not using the fake provider) - generate/paste them at that point, not in the YAML file.
4. After the first deploy, open a shell for the web service (Render dashboard → your service → **Shell**) and run:
   ```bash
   alembic upgrade head
   ```
5. Your API is live at `https://<service-name>.onrender.com/docs`.

### render.yaml

```yaml
services:
  - type: web
    name: skillforge-ai-api
    runtime: docker
    dockerfilePath: ./docker/Dockerfile
    dockerContext: .
    healthCheckPath: /health
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: skillforge-ai-db
          property: connectionString
      - key: REDIS_URL
        fromService:
          name: skillforge-ai-redis
          type: keyvalue
          property: connectionString
      - key: JWT_SECRET_KEY
        sync: false
      - key: AI_PROVIDER
        value: fake
      - key: CORS_ORIGINS
        value: '["https://skillforge-ai-api.onrender.com"]'

  - type: keyvalue
    name: skillforge-ai-redis
    plan: free
    ipAllowList: []

databases:
  - name: skillforge-ai-db
    databaseName: skillforge
    user: skillforge
    plan: free
```

This file is written against Render's documented Blueprint spec but hasn't been deployed and verified end to end from this environment (no Render account available here) - double-check field names against [render.com/docs/blueprint-spec](https://render.com/docs/blueprint-spec) if something doesn't provision as expected, particularly the Redis service `type` (`keyvalue` is current; older guides use `redis`, which Render treats as a deprecated alias for the same thing).

Once it's live, update the README's `git clone <this-repo>` block with the real URL, and add `https://<service-name>.onrender.com/docs` as the linked demo.

## 3. Deploying elsewhere

The container itself (`docker/Dockerfile`) is standard and portable - the same image runs on Railway, Fly.io, a plain VPS with `docker compose`, or a Kubernetes cluster. What changes per platform is only how you provide `DATABASE_URL`/`REDIS_URL` and run the migration step once before traffic hits the new instance. If you deploy elsewhere, the table in section 1 is the complete list of what the app needs to know about.

## 4. Smoke-testing a deployment

Once something is live, this should all succeed against the real URL:

```bash
BASE_URL=https://your-deployment.example python scripts/load_test.py --base-url "$BASE_URL" --concurrency 2 --requests-per-worker 3
```

If that runs clean, registration, login, and the full interview loop are working against the real database and Redis instance, not just locally.
