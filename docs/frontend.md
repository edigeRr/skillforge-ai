# Frontend

A plain HTML/CSS/JS frontend for SkillForge AI. No framework, no build step, no separate service — it's static files served by the same FastAPI app that serves the API, talking to that API purely over `fetch()`.

## Why no framework

The backend already has a fully documented, tested REST API (see [api.md](api.md)). Adding React or Vue here would mean a second toolchain, a build step, and a second deploy target for what's fundamentally a handful of pages. Plain JS keeps it to one container, one `docker compose up`, and every line of it is something you can read top to bottom without knowing a framework first.

## Design concept

The theme is a forge, worked after hours — SkillForge, taken literally. Two things carry it:

- **Color as temperature.** Scores and difficulty both use the same heat scale, from dull ember-red at the low end to white-gold at the high end — the same way heated metal actually changes color as it gets hotter. This is the one place the design spends real boldness; it shows up on score badges, the difficulty picker, and dashboard topic strength.
- **Type.** Big Shoulders for headings (an industrial, steel-heritage typeface — not decorative, actually about steel), IBM Plex Sans for body text, IBM Plex Mono for anything data-like (scores, topics, timestamps).

Dark background throughout — a forge is dark except for what's glowing.

## Structure

```
static/
├── index.html          landing page
├── css/
│   ├── style.css        shared design tokens, typography, base components (buttons, cards, chips, nav)
│   └── home.css          landing-page-specific layout
└── js/
    ├── api.js            fetch wrapper: token storage, auto-refresh on 401, unified error handling
    ├── nav.js             shared nav auth-state toggle + logout, included on every page
    └── hero.js            landing page typewriter effect

app/web/
└── routes.py            FastAPI routes that serve the static HTML pages (kept out of the OpenAPI schema)
```

Each page is a self-contained `.html` file with its own `<script>` tags — no templating layer, so nav/footer markup is duplicated per page rather than shared through includes. That's a deliberate trade for "no build step, every file readable on its own."

## How auth works on the frontend

`api.js` stores the access and refresh tokens in `localStorage` after login. Every request through `SkillForge.api.*` attaches `Authorization: Bearer <token>` automatically. If a request comes back `401`, `api.js` transparently calls `/api/v1/auth/refresh` once and retries the original request — the same rotation logic the backend enforces (old refresh token revoked, new one issued) is just being driven from the browser now instead of from a test client.

`nav.js` reads that same login state to show/hide the right nav links (`[data-auth="logged-in"]` vs `[data-auth="logged-out"]`) and wires up logout.

## Progress

- **v1.1** — static file serving + page routing wired into the FastAPI app (`app/web/routes.py`, `StaticFiles` mount in `main.py`, `Dockerfile`/`docker-compose.yml` updated to ship `static/`). Placeholder page only.
- **v1.2** — design system (`style.css`: color tokens, typography, buttons, cards, chips) and the API client (`api.js`: fetch wrapper, token storage, auto-refresh).
- **v1.3** — the real landing page (`home.css`, `nav.js`, `hero.js`, full `index.html`).
