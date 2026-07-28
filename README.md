# SkillForge AI

AI-powered mock technical interview platform. Pick a language and difficulty, get interviewed by an LLM, receive scored feedback, and track your progress over time.

> Under active development. The full README (architecture diagram, screenshots, live demo link) lands at the end of the roadmap — see [docs/roadmap.md](docs/roadmap.md), Sprint 6.

## Docs

- [Vision](docs/vision.md)
- [Requirements](docs/requirements.md)
- [Architecture](docs/architecture.md)
- [Database design](docs/database.md)
- [API specification](docs/api.md)
- [Roadmap](docs/roadmap.md)

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

API available at `http://localhost:8000`, interactive docs at `http://localhost:8000/docs`, health check at `http://localhost:8000/health`.

## Tech stack

FastAPI · SQLAlchemy (async) · PostgreSQL · Redis · Alembic · Docker · pytest · GitHub Actions

## License

MIT — see [LICENSE](LICENSE).
