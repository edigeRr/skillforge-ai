# Contributing

This is currently a solo learning/portfolio project, but it is built the way a real team project would be.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```

## Running tests

```bash
pytest --cov=app --cov-report=term-missing
```

## Branch naming

`feature/<short-description>`, `fix/<short-description>`, `chore/<short-description>`.

## Commit style

Short, imperative subject line ("Add refresh token rotation", not "Added" or "Adding"). Reference the roadmap task ID where relevant, e.g. `SF-24: implement AuthService.register`.
