# SkillForge AI — Roadmap

Six sprints, ~1.5–2 weeks each (roughly 10–12 weeks total at a part-time pace). Each sprint has a goal, a Definition of Done, and a task list. Task IDs are for tracking in GitHub Projects / Jira — split any task further if it doesn't fit in a day or two.

**Where things stand:** Sprints 1–6 shipped as the backend release `v1.0.0` (last commit 2026-08-03). After that came the browser frontend (`v1.1.0`, 2026-10-22), then a live demo, an admin area and small fixes (`v1.2.0`, 2026-10-23). Those later stages are at the end of this file, in the same format, with tasks numbered on from SF-89.

## Sprint 1 — Project Foundation
**Goal:** empty-but-real project that runs end to end with `docker compose up`.
**Definition of Done:** a fresh clone + `docker compose up` gives a running API with a working `/health` endpoint and a CI pipeline that's green on an empty test suite.

- SF-1 Initialize git repo, `.gitignore`, MIT `LICENSE`
- SF-2 `pyproject.toml` with FastAPI, SQLAlchemy (async), Alembic, pydantic-settings, uvicorn
- SF-3 Base FastAPI app (`app/main.py`) with a `/health` stub
- SF-4 `app/core/config.py` — Pydantic settings loaded from env
- SF-5 `.env.example` with all required variables documented
- SF-6 `docker/Dockerfile` (multi-stage: deps, then runtime)
- SF-7 `docker-compose.yml`: api + postgres + redis
- SF-8 Async SQLAlchemy engine + session setup (`app/db/session.py`)
- SF-9 Redis client setup (`app/db/redis.py`)
- SF-10 Alembic init + first (empty) migration wired to the async engine
- SF-11 `app/core/logging.py` — structured JSON logging with request ID
- SF-12 `app/core/exceptions.py` — base `AppException` + FastAPI exception handler mapping to the error envelope
- SF-13 Real `/health` implementation (checks DB + Redis)
- SF-14 Pre-commit config: black, isort, ruff
- SF-15 `.github/workflows/ci.yml`: install deps, lint, run pytest (must be green even with zero tests)
- SF-16 `CONTRIBUTING.md` — how to run locally, run tests, branch naming
- SF-17 `README.md` skeleton (title, one-paragraph description, "docs coming soon")

## Sprint 2 — Authentication
**Goal:** register, login, refresh, logout, all tested.
**Definition of Done:** a script can register a user, log in, hit a protected endpoint, refresh, and log out.

- SF-18 `User` SQLAlchemy model + Alembic migration
- SF-19 `RefreshToken` SQLAlchemy model + migration
- SF-20 `UserRepository` (create, get_by_email, get_by_id)
- SF-21 `RefreshTokenRepository` (create, get_by_hash, revoke, revoke_all_for_user)
- SF-22 Password hashing utility (bcrypt/argon2 wrapper)
- SF-23 JWT utility: create access token, create refresh token, decode/verify
- SF-24 `AuthService.register()` with email-uniqueness check
- SF-25 `AuthService.login()` with generic invalid-credentials error
- SF-26 `AuthService.refresh()` with rotation (old token revoked, new one issued)
- SF-27 `AuthService.logout()`
- SF-28 Pydantic schemas: `RegisterRequest`, `LoginRequest`, `TokenResponse`, `UserResponse`
- SF-29 `POST /auth/register` route
- SF-30 `POST /auth/login` route
- SF-31 `POST /auth/refresh` route
- SF-32 `POST /auth/logout` route
- SF-33 `get_current_user` FastAPI dependency (decodes bearer token)
- SF-34 Rate limiting on `/auth/login` and `/auth/register` (per-IP, e.g. via `slowapi` or a Redis token bucket)
- SF-35 Unit tests: `AuthService` (repositories mocked)
- SF-36 Integration tests: register → login → access protected route → refresh → logout, against a real test DB
- SF-37 `GET /profile/me`, `PUT /profile/me` routes + service methods

## Sprint 3 — Interview Core
**Goal:** the full interview loop works against a fixed/fake question source (no real AI yet).
**Definition of Done:** start → answer → answer → finish works end to end, covered by integration tests, with a stub `FakeAIProvider`.

- SF-38 `Interview` SQLAlchemy model + migration
- SF-39 `Question` SQLAlchemy model + migration
- SF-40 `InterviewRepository` (create, get_by_id, get_active_for_user, list_by_user paginated)
- SF-41 `QuestionRepository` (create, get_by_id, list_by_interview ordered)
- SF-42 `BaseAIProvider` abstract interface (`generate_question`, `evaluate_answer`)
- SF-43 `FakeAIProvider` for tests/dev (deterministic canned responses)
- SF-44 `InterviewService.start()` — enforces "one active interview per user"
- SF-45 `InterviewService.answer()` — validates ownership, records answer, calls provider, advances or completes
- SF-46 `InterviewService.finish()` — early termination, partial scoring
- SF-47 Overall-score computation (average of answered questions)
- SF-48 Pydantic schemas: `StartInterviewRequest`, `InterviewResponse`, `AnswerRequest`, `AnswerResponse`, `QuestionResponse`
- SF-49 `POST /interviews` route
- SF-50 `POST /interviews/{id}/answer` route
- SF-51 `POST /interviews/{id}/finish` route
- SF-52 `GET /interviews/{id}` route
- SF-53 `GET /interviews` (history, paginated, filterable) route
- SF-54 Unit tests: `InterviewService` against `FakeAIProvider`
- SF-55 Integration tests: full interview lifecycle
- SF-56 Edge-case tests: answering someone else's interview (403/404), double-starting an interview (409), answering an already-answered question (409)

## Sprint 4 — Real AI Integration
**Goal:** swap `FakeAIProvider` for a real LLM in at least one environment.
**Definition of Done:** a real interview against Claude or GPT produces a sensible question and a sensible evaluation, with graceful failure if the provider is down.

- SF-57 Prompt template: question generation (language, difficulty, exclude-topics list)
- SF-58 Prompt template: answer evaluation (question, answer → score + feedback, structured output)
- SF-59 `AnthropicProvider` implementing `BaseAIProvider`
- SF-60 `OpenAIProvider` implementing `BaseAIProvider` (second implementation, proves the interface is real)
- SF-61 Provider selection via config (`AI_PROVIDER=anthropic|openai`)
- SF-62 Structured-output parsing + validation (reject/retry on malformed model output)
- SF-63 Timeout + retry-with-backoff wrapper around provider calls
- SF-64 Graceful error path: provider failure returns a clean `503 AI_PROVIDER_UNAVAILABLE`, never a bare 500
- SF-65 Redis-backed cache of recently generated questions per (language, difficulty) to cut duplicate generation calls
- SF-66 Cost/latency logging per AI call (model, tokens if available, duration)
- SF-67 Integration test hitting a real provider, gated behind an env flag so CI doesn't need live API keys by default
- SF-68 Manual QA pass: run 5 full interviews per language, sanity-check question quality and scoring

## Sprint 5 — Dashboard, Hardening, Testing
**Goal:** dashboard is accurate and cached; coverage target is met; security review done.

- SF-69 Dashboard aggregation query (total interviews, average score, per-topic averages)
- SF-70 `DashboardService` with the "min 2 data points per topic" rule
- SF-71 Redis caching of dashboard stats with invalidation on interview completion
- SF-72 `GET /dashboard/stats` route
- SF-73 Unit tests: `DashboardService` (including the min-data-points edge case)
- SF-74 Integration test: stats reflect real interview data end to end
- SF-75 Coverage report wired into CI; fail the build under 80% on `app/services` and `app/api`
- SF-76 Security pass: confirm no secrets in logs, CORS origins locked down, rate limits cover all write endpoints
- SF-77 Basic load test (e.g. locust or a simple async script) against `/interviews/{id}/answer` to sanity-check latency under concurrency
- SF-78 Pagination edge cases tested (empty list, last page, `page_size` cap)
- SF-79 Consistent error-code audit — every documented `error_code` in api.md actually gets raised somewhere and is tested

## Sprint 6 — Documentation & Release
**Goal:** the repo looks like a real, released product.

- SF-80 Full `README.md`: description, screenshots/GIF, tech stack, architecture diagram, setup instructions, API summary, roadmap link
- SF-81 Polish FastAPI route docstrings/examples so `/docs` (Swagger UI) is genuinely useful, not just auto-generated boilerplate
- SF-82 Export ER diagram and architecture diagram as images for the README
- SF-83 `docs/deployment.md` — how to run in production-like mode (env vars, migrations, secrets)
- SF-84 Record a short demo GIF/video of a full interview flow
- SF-85 Tag `v1.0.0` release with release notes
- SF-86 Final smoke test: fresh clone → `docker compose up` → full interview flow, zero manual fixes
- SF-87 Deploy a live demo instance (e.g. Render/Railway/Fly.io) so the README can link a working URL, not just code
- SF-88 Add repo topics/description on GitHub for discoverability

## Frontend — `v1.1.0`
**Goal:** everything the API does is usable from a browser, served by the same FastAPI app with no build step.
**Definition of Done:** sign up, log in, run a full interview, browse history and read the dashboard in a browser; every page has jsdom tests; CI runs them and a Docker smoke test.

Built in stages v1.1–v1.11; the per-stage detail is in [frontend.md](frontend.md#progress).

- SF-89 Static file serving and page routes (`app/web/routes.py`), `static/` shipped in the Docker image
- SF-90 Design system (`style.css`, heat scale `--heat-0…10`) and the API client `api.js` (tokens, refresh on 401)
- SF-91 Landing page, sign-up `/register`, log-in `/login`
- SF-92 `guard.js` for members-only pages
- SF-93 Interview start `/interview` and session `/interview/{id}`; `total_questions` added to the interview API
- SF-94 History `/history` (filters, pages, state in the address bar) and dashboard `/dashboard`
- SF-95 Favicon, 404 page, a nav that fits 320px screens
- SF-96 `scripts/preview_server.py` — real pages and schemas with an in-memory API, for checking pages without Docker
- SF-97 CI jobs `frontend` (jsdom tests) and `docker` (build, start, `curl` the pages)

## Live demo
**Goal:** a working public URL for the README (this is SF-87).
**Definition of Done:** the Blueprint deploys from `main` on its own, and the deployed app passes `/health` with the database and Redis up.

- SF-98 `render.yaml` Blueprint: web service, Postgres 16 and Key Value on the free plan
- SF-99 Rewrite Render's `postgresql://` URLs to the asyncpg driver
- SF-100 `docker/start.sh`: migrations, then uvicorn on Render's `PORT`, behind the proxy with real client IPs
- SF-101 Close the database to outside connections (`ipAllowList: []`)
- SF-102 [deployment.md](deployment.md) rewritten around the real Blueprint, the demo linked from the README

## Admin area — `v1.2.0`
**Goal:** accounts with an admin role can manage other accounts; roles can grow past two.
**Definition of Done:** an admin can list accounts, create one and change roles from `/admin`; everyone else gets `403`; the first admin can be made without the API.

- SF-103 `role` column (plain string, default `user`) with a migration
- SF-104 `require_admin` dependency; `403 ADMIN_REQUIRED`
- SF-105 `GET/POST /admin/users`, `PATCH /admin/users/{id}/role` (an admin can't change their own role)
- SF-106 `scripts/make_admin.py` for the first admin
- SF-107 `/admin` page, and an Admin link in the nav from a `role` claim in the access token (a display hint only)
- SF-108 `Cache-Control: no-cache` on pages and static files; `[hidden]` that always wins over `display` rules

## Small fixes after `v1.2.0`
- SF-109 Tests always use `<name>_test`, never the dev database
- SF-110 Dashboard topic lists picked without overlap in `DashboardService`
- SF-111 404 page for a mistyped interview id
- SF-112 Field-level messages for a `422` on sign-up, log-in and admin
- SF-113 Chip borders at WCAG contrast

## Open
- `total_questions` comes from the current `INTERVIEW_QUESTION_COUNT`, not from the interview itself, so changing the setting would change what old interviews show. Needs a column and a migration if the setting ever changes.
- A few lines over 100 characters in the older frontend tests (`register.test.mjs`, `login.test.mjs`, `session.test.mjs`); there's no JS formatter.
