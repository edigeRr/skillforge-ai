# SkillForge AI

AI-powered mock technical interview platform. Pick a language and a difficulty, get interviewed question by question, receive a scored evaluation and specific feedback on each answer, and track how you're trending over time.

**Live demo:** https://skillforge-ai-t78b.onrender.com (free hosting: the first load after a quiet spell can take about a minute).

It runs as one FastAPI app: a tested REST API and a browser UI on top of it — sign up, start an interview, answer questions one at a time, and see your scores, history and dashboard. Everything is also reachable straight through the interactive API docs at `/docs`.

## Quick look

```
POST /api/v1/interviews          {"language": "python", "difficulty": "middle"}
  -> first question

POST /api/v1/interviews/{id}/answer   {"question_id": "...", "answer": "..."}
  -> score, feedback, next question (or "completed" once the session is done)

GET  /api/v1/dashboard/stats
  -> total interviews, average score, strongest and weakest topics
```

That's the whole product loop. Full request/response shapes are in [docs/api.md](docs/api.md), or just try it live in Swagger at `/docs` (see [Try it](#try-it) below).

## Frontend

Plain HTML, CSS and JavaScript served by the same FastAPI app — no framework, no build step, one container. The design takes "forge" literally: scores and difficulty share one heat scale, from dull ember-red to white-gold.

| Page | What it does |
|---|---|
| `/` | Landing page |
| `/register`, `/login` | Sign up and log in; tokens are stored and refreshed by a small API client |
| `/interview` | Pick a language and a level; offers to resume an interview already in progress |
| `/interview/{id}` | One question at a time, the score on the heat scale with feedback, then a full summary |
| `/history` | Past interviews with filters and pages, kept in the address bar |
| `/dashboard` | Completed interviews, average score, strongest and weakest topics |
| `/admin` | For admins: create accounts and change roles |

Members-only pages send logged-out visitors to `/login`, and unknown addresses get a proper 404 page. Details in [docs/frontend.md](docs/frontend.md).

## Architecture

![Architecture diagram](docs/images/architecture.png)

FastAPI on top of a layered `api -> service -> repository -> model` structure, so business rules never depend on the web framework or the ORM directly. The AI integration sits behind a `BaseAIProvider` interface (Strategy pattern) — `AnthropicProvider` and `OpenAIProvider` are thin, swappable implementations behind a shared retry/backoff/JSON-parsing base class, and a `FakeAIProvider` means the whole app runs and is fully testable with zero API keys. Full writeup in [docs/architecture.md](docs/architecture.md).

## Tech stack

FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Alembic · JWT auth · Docker Compose · pytest · plain HTML/CSS/JS · jsdom · GitHub Actions

## Try it

```bash
git clone https://github.com/edigeRr/skillforge-ai.git
cd skillforge-ai
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000` and create an account — you land straight on the interview page. No API key needed: `AI_PROVIDER` defaults to a deterministic fake provider, so the whole loop works out of the box.

Prefer the raw API? `http://localhost:8000/docs` is a full interactive Swagger UI: register, log in, click **Authorize** and paste `Bearer <access_token>`, then start an interview and answer questions from there.

No Docker? `python scripts/preview_server.py` serves the same pages against an in-memory stand-in for the API, so the UI can be clicked through without Postgres or Redis (see [docs/frontend.md](docs/frontend.md#previewing-without-docker)).

Want a real LLM instead of the fake one? Set `AI_PROVIDER=anthropic` (or `openai`) and the matching `*_API_KEY` in `.env`, then restart.

```bash
# once you have a key, a quick multi-language sanity check:
AI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-... python scripts/manual_qa.py
```

## Data model

![ER diagram](docs/images/database-er.png)

Four tables: `users`, `refresh_tokens`, `interviews`, `questions`. A partial unique index enforces "one active interview per user" at the database level, not just in application code. Full schema in [docs/database.md](docs/database.md).

## Testing

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db redis
pytest --cov=app --cov-report=term-missing
```

102 backend tests (unit + integration, against a real Postgres/Redis, not mocks-all-the-way-down), with coverage of `app/services` and `app/api` enforced at 80%+ as a CI gate. One of them is a live-provider test, skipped unless `RUN_LIVE_AI_TESTS=1` and a real API key are set, so CI never needs credentials.

The frontend has 102 tests that run the real `static/js` files against the real pages in jsdom, with the API replaced by a scripted fake (Node.js 20+):

```bash
cd tests-frontend
npm install
npm test
```

CI runs three jobs on every push to `main` and every pull request: lint and backend tests, frontend tests, and a Docker job that builds the image, starts it and checks that the pages are served.

There's also a basic concurrency/latency check for the answer-evaluation endpoint:

```bash
python scripts/load_test.py
```

## API

Full spec with every endpoint, request/response schema, and error code: [docs/api.md](docs/api.md). Interactive version at `/docs` once the app is running.

| | |
|---|---|
| Auth | `POST /auth/register`, `/login`, `/refresh`, `/logout` |
| Profile | `GET/PUT /profile/me` |
| Interview | `POST /interviews`, `/interviews/{id}/answer`, `/interviews/{id}/finish`, `GET /interviews/{id}`, `GET /interviews` |
| Dashboard | `GET /dashboard/stats` |
| Admin | `GET/POST /admin/users`, `PATCH /admin/users/{id}/role` (admin role only) |

## Docs

- [Vision](docs/vision.md) — what this is and isn't
- [Requirements](docs/requirements.md) — functional + non-functional, with acceptance criteria
- [Architecture](docs/architecture.md) — layering, patterns, tech choices
- [Database design](docs/database.md) — schema, indexes, ER diagram
- [API specification](docs/api.md) — every endpoint
- [Frontend](docs/frontend.md) — pages, design, auth in the browser, tests
- [Roadmap](docs/roadmap.md) — sprint-by-sprint task breakdown
- [Deployment guide](docs/deployment.md) — running this outside Docker Compose

## Roadmap

- [x] Sprint 1 — Project scaffold (Docker, CI, structured logging, health check)
- [x] Sprint 2 — Auth (JWT access/refresh, bcrypt, rate limiting)
- [x] Sprint 3 — Interview core (state machine, scoring)
- [x] Sprint 4 — Real AI integration (Anthropic/OpenAI providers, caching, retries)
- [x] Sprint 5 — Dashboard, hardening, load testing
- [x] Sprint 6 — Docs, diagrams, v1.0.0 release
- [x] Frontend — sign-up, log-in, interview session, history and dashboard pages, with jsdom tests
- [x] Live demo on Render — Blueprint, migrations on start, database closed to outside traffic
- [x] Admin area — roles, admin-only endpoints, `/admin` page and an Admin link in the nav

Full task-level detail: [docs/roadmap.md](docs/roadmap.md).

## License

MIT — see [LICENSE](LICENSE).
