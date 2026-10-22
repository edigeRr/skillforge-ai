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
├── index.html           landing page
├── register.html        sign-up page
├── login.html           log-in page
├── css/
│   ├── style.css         shared design tokens, typography, base components (buttons, cards, chips, nav)
│   ├── forms.css          form fields, labels, hints and the invalid state
│   ├── auth.css           card layout shared by the sign-up and log-in pages
│   └── home.css           landing-page-specific layout
└── js/
    ├── api.js             fetch wrapper: token storage, auto-refresh on 401, unified error handling
    ├── nav.js              shared nav auth-state toggle + logout, included on every page
    ├── hero.js             landing page typewriter effect
    ├── register.js         sign-up form: register, log in, error messages
    └── login.js            log-in form: log in, store tokens, error messages

app/web/
└── routes.py            FastAPI routes that serve the static HTML pages (kept out of the OpenAPI schema)

tests-frontend/
├── package.json         jsdom is the only dependency; `npm test` runs Node's built-in test runner
├── register.test.mjs    sign-up form tests
└── login.test.mjs       log-in form tests
```

Each page is a self-contained `.html` file with its own `<script>` tags — no templating layer, so nav/footer markup is duplicated per page rather than shared through includes. That's a deliberate trade for "no build step, every file readable on its own."

## How auth works on the frontend

`api.js` stores the access and refresh tokens in `localStorage` after login. Every request through `SkillForge.api.*` attaches `Authorization: Bearer <token>` automatically. If a request comes back `401`, `api.js` transparently calls `/api/v1/auth/refresh` once and retries the original request — the same rotation logic the backend enforces (old refresh token revoked, new one issued) is just being driven from the browser now instead of from a test client.

`nav.js` reads that same login state to show/hide the right nav links (`[data-auth="logged-in"]` vs `[data-auth="logged-out"]`) and wires up logout.

## Sign-up page (`/register`)

The form asks for a name, an email and a password. The browser's own validation runs first — required fields, a real email address, a password of 8–72 characters, a name that isn't only spaces — so most mistakes never reach the server. The one rule a browser can't express, "at least one letter and one digit", is enforced by the API and reported back.

On submit, `register.js`:

1. locks the button, so a double click can't send two requests;
2. calls `POST /auth/register`;
3. calls `POST /auth/login` with the same credentials and stores the returned tokens;
4. sends the user to the home page, where the nav switches to the logged-in links. This will become the interview page once that page exists.

Problems are shown in one banner above the form. It has `role="alert"`, so screen readers announce it.

| Situation | What the user sees |
|---|---|
| `409 EMAIL_ALREADY_EXISTS` | "An account with that email already exists - try logging in instead." The email field gets a red border, `aria-invalid="true"` and focus; the mark clears as soon as the user edits the field. |
| `422` | "Please check your details. A password needs 8+ characters with at least one letter and one digit." |
| `429` | "Too many attempts - wait a minute and try again." Register and login share a limit of 5 requests per minute per IP. |
| Server unreachable | "Can't reach the server. Check your connection and try again." |
| Account created, automatic log-in failed | "Your account was created, but signing you in failed. Please log in." |
| Anything else | "Something went wrong. Please try again." |

Form fields use `--text-faint` for their border so the field boundary keeps a contrast of at least 3:1 against the card, as WCAG 2.1 asks for interface components.

## Log-in page (`/login`)

The form asks for an email and a password, using the same card (`auth.css`) and fields (`forms.css`) as the sign-up page. The browser checks first that both are filled in and that the email looks like an email. The password field has `autocomplete="current-password"`, so password managers offer the saved password.

On submit, `login.js` locks the button, calls `POST /auth/login`, stores the returned tokens and sends the user to the home page. The request is sent without an access token, so a wrong password never triggers the automatic token refresh in `api.js`.

| Situation | What the user sees |
|---|---|
| `401 INVALID_CREDENTIALS` | "Incorrect email or password." The API gives the same answer for an unknown email and a wrong password, so neither field is marked: the page can't know which one is wrong, and saying so would reveal which emails have accounts. |
| `429` | "Too many attempts - wait a minute and try again." The limit is shared with sign-up. |
| Server unreachable | "Can't reach the server. Check your connection and try again." |
| Anything else | "Something went wrong. Please try again." |

## Tests

**Pages (backend).** `tests/integration/test_pages.py` checks that every page route returns HTML, that every `/static/...` file a page references is actually served, and that the page routes stay out of the OpenAPI schema. It runs with the rest of the backend suite.

**Forms (frontend).** `tests-frontend/` runs the real `static/js/*.js` files against the real `static/*.html` pages inside jsdom, with `fetch` replaced by a scripted fake API. Node's built-in test runner does the running, so jsdom is the only dependency.

```bash
cd tests-frontend
npm install
npm test
```

This needs Node.js 20 or newer. The sign-up tests cover the happy path (register, log in, tokens stored, redirect), every message in the table above, the double-submit guard, and the native validation rules whose limits must match the API schema (password 8–72, name up to 100).

The log-in tests cover the happy path (tokens stored, redirect), every message in the log-in table, that a wrong password does not start a token refresh, that an old error disappears on the next try, the double-submit guard, native validation, and the `autocomplete` values password managers rely on.

jsdom does no layout and can't follow a real navigation, so these tests say nothing about how a page looks or where the browser lands next.

## Progress

- **v1.1** — static file serving + page routing wired into the FastAPI app (`app/web/routes.py`, `StaticFiles` mount in `main.py`, `Dockerfile`/`docker-compose.yml` updated to ship `static/`). Placeholder page only.
- **v1.2** — design system (`style.css`: color tokens, typography, buttons, cards, chips) and the API client (`api.js`: fetch wrapper, token storage, auto-refresh).
- **v1.3** — the real landing page (`home.css`, `nav.js`, `hero.js`, full `index.html`).
- **v1.4** — sign-up: `register.html`, `forms.css`, `auth.css`, `register.js`, the `/register` route, backend page tests and the first frontend tests.
- **v1.5** — log-in: `login.html`, `login.js`, the `/login` route, page and jsdom tests.

## What's next

- Guards that send logged-out visitors from `/interview`, `/dashboard` and `/history` to `/login`.
- The interview start page and the interview session: question, answer box, score shown on the heat scale.
- History and dashboard pages.
- An admin area. Backend first — a `role` column, an admin-only dependency, endpoints to create accounts and change roles — then a page for it. Roles are meant to grow beyond `admin` and `user`.
- Running the frontend tests in CI.
