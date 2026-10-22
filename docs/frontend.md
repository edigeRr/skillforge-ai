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
├── interview.html       interview start form: language and level (members only)
├── session.html         one interview session at /interview/{id}: question, answer, score, summary (members only)
├── history.html         past interviews with filters and pages (members only)
├── dashboard.html       progress overview: totals, average, strongest and weakest topics (members only)
├── admin.html           accounts: create one, change roles (admin role only)
├── 404.html             page-not-found page for unknown addresses
├── favicon.svg          the ember dot from the logo, on every page
├── css/
│   ├── style.css         shared design tokens, typography, base components (buttons, cards, chips, nav)
│   ├── forms.css          form fields, labels, hints and the invalid state
│   ├── auth.css           card layout shared by the sign-up and log-in pages
│   ├── interview.css      start form: language and level chips
│   ├── score.css          score meter shared by the session and history pages
│   ├── session.css        question, answer box, summary
│   ├── history.css        history list, filters, pagination
│   ├── dashboard.css      dashboard tiles and topic lists
│   ├── admin.css          create-account form, account cards, pagination
│   └── home.css           landing-page-specific layout
└── js/
    ├── api.js             fetch wrapper: token storage, auto-refresh on 401, unified error handling
    ├── nav.js              shared nav auth-state toggle + logout, included on every page
    ├── guard.js            sends logged-out visitors from members-only pages to /login
    ├── hero.js             landing page typewriter effect
    ├── register.js         sign-up form: register, log in, error messages
    ├── interview.js        start form: start an interview or offer to resume the open one
    ├── heat.js             heatLevel / heatColor / paintScore: a 0-10 score on the heat scale
    ├── session.js          interview session: answer, score, next question, finish, summary
    ├── history.js          history: list, filters, pages, state kept in the address bar
    ├── dashboard.js        dashboard: stats, topics, greeting
    ├── admin.js            admin: list accounts, create one, change roles
    └── login.js            log-in form: log in, store tokens, error messages

app/web/
└── routes.py            FastAPI routes that serve the static HTML pages (kept out of the OpenAPI schema)

tests-frontend/
├── package.json         jsdom is the only dependency; `npm test` runs Node's built-in test runner
├── register.test.mjs    sign-up form tests
├── login.test.mjs       log-in form tests
├── interview.test.mjs   interview start form tests
├── session.test.mjs     interview session tests
├── history.test.mjs     history page tests
├── dashboard.test.mjs   dashboard tests
├── admin.test.mjs       admin page tests
└── guard.test.mjs       members-only page guard tests
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
4. sends the user to `/interview`, so a new account goes straight to starting a first interview.

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

## Members-only pages (`/interview`, `/history`, `/dashboard`, `/admin`)

These pages load `api.js` and `guard.js` in `<head>`, before the page body. If there is no access token in `localStorage`, `guard.js` calls `location.replace("/login")`. Because the page is *replaced* rather than navigated away from, the Back button on the log-in page doesn't bounce the visitor back into the guard.

The guard only checks that a token is stored, not that it is still valid. That is enough: an expired token is refreshed by `api.js` on the first `401`, and if the refresh fails too, `api.js` clears the tokens and sends the user to `/login` itself. The guard is a convenience, not a security boundary — every piece of data on these pages comes from API endpoints that check the token on the server.


## Starting an interview (`/interview`)

The start form has two groups of chips: language (Python, Java, C++, JavaScript) and level (Junior, Middle, Senior). Each chip is a real radio button inside a `<label>`; the button itself is visually hidden and the label is styled as the chip. That keeps the native behavior for free: arrow keys move within a group, a screen reader announces "Language, radio group", and `required` on each group means the browser won't submit until both are picked. A selected level chip takes its border color from the heat scale — the higher the level, the hotter the metal.

On submit, `interview.js` locks the button, calls `POST /interviews` and sends the user to `/interview/{id}`. The route only accepts an id shaped like a UUID.

| Situation | What the user sees |
|---|---|
| `409 INTERVIEW_ALREADY_IN_PROGRESS` | The page asks `GET /interviews?status=in_progress&page_size=1` for the open interview and shows "You already have an interview in progress" with a "Continue that interview" button linking to it. Focus moves to the button. |
| `409`, and the open interview can't be loaded | "You already have an interview in progress, but it couldn't be loaded. Please try again." |
| `429` | "Too many requests - wait a minute and try again." Starting an interview counts toward the limit of 30 write requests per minute. |
| Server unreachable | "Can't reach the server. Check your connection and try again." |
| Anything else | "Something went wrong. Please try again." |

A `401` never reaches this table: `api.js` refreshes the token, or sends the user to `/login` if that fails.

## Interview session (`/interview/{id}`)

The page loads `GET /interviews/{id}` and picks a view from it:

- **In progress** — the first question without an answer, labelled "Question N · topic", with an answer box that gets focus. Reloading the page mid-interview lands on the same question, because the state lives on the server, not in the browser.
- **Scored** — after `POST /interviews/{id}/answer`: the score out of 10, a bar filled to the score and colored on the heat scale, and the feedback. "Next question" shows the question that came back with the score; after the last one the button says "See results" and loads the finished interview.
- **Summary** — for a completed interview, or right after "Finish early" (`POST /interviews/{id}/finish`, after a `confirm()`): the overall score and every question with the answer, its score and feedback. Unanswered questions say "Not answered." If nothing was scored, the page says so instead of showing 0.
- **Not found** — the API answers `404` for an interview that belongs to someone else as well as for one that doesn't exist, and the page doesn't try to tell them apart.

`heat.js` turns a score into a heat level by steps of two points — 0–1.9 is `--heat-0`, 2–3.9 is `--heat-2`, and so on up to exactly 10 for `--heat-10` — and `heatColor(score)` returns the matching `var(--heat-N)`. The number itself stays in the normal text color: the darkest heat colors would be unreadable as text on the dark background, so the color lives on the bar, not on the digits. The bar is a `role="meter"` with `aria-valuenow`, so screen readers announce "7.5 out of 10".

Answers are user text, so they're always put on the page with `textContent`, never as HTML.

| Situation | What the user sees |
|---|---|
| Answer is empty or only spaces | "Write an answer before submitting." Nothing is sent. |
| `409` (question already answered, or interview no longer in progress — say, finished in another tab) | The page reloads the interview, shows its current state and says "This interview changed since the page loaded - here is its latest state." |
| `429` | "Too many requests - wait a minute and try again." |
| Server unreachable | "Can't reach the server. Check your connection and try again." |
| Anything else | "Something went wrong. Please try again." |

On every error the answer stays in the box, so nothing typed is lost. While an answer is being scored, the box is read-only and both buttons are disabled.

The counter reads "Question 2 of 5". Both numbers come from the API — `order_index` counts from 1 and `total_questions` mirrors `INTERVIEW_QUESTION_COUNT` in the backend settings — so the page never hard-codes 5. If `total_questions` is missing, it falls back to "Question 2".

## History (`/history`)

The page lists the user's interviews from `GET /interviews`, newest first, ten per page. Each row is a link to `/interview/{id}` and shows the language and level, the start date (`<time datetime>`, formatted in the browser's own locale) and, on the right, the score on the heat scale. An interview without a score shows its status instead: "In progress · Continue" for the open one, "Completed · No score" for one finished before any answer.

Three dropdowns filter by language, level and status. Changing one goes back to page 1. Below the list, "Previous" / "Next" and "Page 2 of 3" appear only when there is more than one page.

The filters and page live in the address bar (`/history?language=python&page=2`) through `history.replaceState`, so a reload or a shared link opens the same view. Values the API would reject — an unknown language, page 0 — are dropped when the page opens, and a page past the end (say `?page=9` with 11 interviews) falls back to the last page instead of showing an empty list.

| Situation | What the user sees |
|---|---|
| No interviews at all | "You haven't done any interviews yet." and a link to start one. |
| Filters match nothing | "No interviews match these filters." and a "Clear filters" button. |
| `429` | "Too many requests - wait a minute and try again." |
| Server unreachable | "Can't reach the server. Check your connection and try again." |
| Anything else | "Something went wrong. Please try again." |

If the user changes filters faster than the server answers, only the newest request is drawn: each request gets a number, and a response that isn't the latest is dropped.

The score meter (`score.css`) and `paintScore` (in `heat.js`) moved out of the session page so both pages draw scores the same way.

## Dashboard (`/dashboard`)

The page reads `GET /dashboard/stats` and shows:

- **Completed interviews** — the count. Interviews still in progress don't count, same as in the API.
- **Average score** — on the heat scale, like every other score. If finished interviews have no scored answers, it says "No scored answers yet." instead of 0.
- **Strongest topics** and **Needs work** — up to three topics each, with their average score. A topic shows up only after at least two scored answers on it (FR-5.1); until then the card explains that instead of staying blank.

The API picks both lists from the same set of topics — the top three and the bottom three — so with three topics or fewer the same topic would land in both. The page drops from "Needs work" any topic already shown under "Strongest topics": calling `arrays` both your best and your worst topic helps no one.

A greeting, "Welcome back, Ada.", comes from `GET /profile/me`. It is loaded separately and is purely decorative: if it fails, the stats still show and no error appears. If the stats fail, the page shows the usual message for `429`, an unreachable server, or anything else. With no finished interviews yet, the stats are replaced by "Finish your first interview to see your stats here" and a "Start an interview" button.

The API caches these stats for five minutes per user, but finishing an interview clears that cache, so the dashboard is current right after the summary screen.

## Admin (`/admin`)

For accounts with the `admin` role. The page loads `GET /profile/me` and the first page of `GET /admin/users` together. Any other logged-in account gets `403` from the API, and the page shows "This page is for administrators" with a link back to the dashboard. `guard.js` still sends logged-out visitors to `/login`, as on every members-only page. The page isn't linked from the nav yet; admins open `/admin` directly.

- **Create an account.** Name, email, password and role, with the same limits as the sign-up form. On success the form clears, "Created nia@example.com as Admin." appears, and the list reloads from page 1 so the new account is on top. A taken email marks the email field; `422`, `429` and an unreachable server get the usual messages.
- **Accounts.** Newest first, 20 per page, with Previous / Next when there is more than one page. Each card shows the name, email and join date, plus a role picker and **Save**. Save stays disabled until the picked role differs from the saved one. On success the status line says "pat@example.com is now Admin."; on failure the picker goes back to the saved role and the error appears above the list. If the account was deleted in the meantime (`404`), the list reloads.
- **Your own card** shows "Admin · you" as text instead of a picker. The API refuses to let an admin change their own role (`409 CANNOT_CHANGE_OWN_ROLE`), so the last admin can't lock everyone out, and the page doesn't offer the control.

Cards instead of a table keep the page readable at 320px with no horizontal scroll: below 640px the role picker moves under the name.

The first admin can't be made through this page or the API. Use `scripts/make_admin.py` (see [docs/api.md](api.md#8-admin)). In the preview server, `POST /api/v1/dev/make-admin` with `{"email": "..."}` does the same.

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

The guard tests open each members-only page with and without stored tokens and check that only the logged-out visit leaves the page, that `guard.js` runs in `<head>` right after `api.js`, and that public pages don't include it. jsdom can't report where a navigation was headed, so the `/login` target is checked in the guard's source and by hand in the browser.

The interview start tests cover starting with the chosen language and level (with the access token attached), the resume offer on `409` and its fallback message, every other message in the table, that the resume offer disappears on the next try, the double-submit guard, native validation for both groups, and that the chips offer exactly the values the API accepts.

The session tests cover opening on the first unanswered question, sending the trimmed answer, the score meter (value, heat level, color, width, `aria-valuenow`), moving to the next question, loading the summary after the last answer, opening a finished interview straight on its summary, answers rendered as text rather than HTML, the no-score case, the "N of M" counter and its fallback, the not-found view, a failed load, the blank-answer check, recovering from a `409`, finishing early with and without confirmation, every error message, the busy lock, and the heat-level steps.

The history tests cover the first load and the row links, score versus status on each row, the empty and no-match states with "Clear filters", filters resetting to page 1 and appearing in the address bar, paging, restoring filters and page from the address bar, dropping values the API would reject, falling back from a page past the end, every error message, and ignoring an older response that arrives after a newer one.

The dashboard tests cover the totals, the average on the heat scale and both topic lists, the greeting and what happens when the profile fails, keeping a topic out of both lists, the explanations for empty topic lists and a missing average, the first-interview state, topic names rendered as text, and every error message.

The admin tests cover the list with a picker on every card but your own, the not-for-administrators view on `403`, saving a changed role (the PATCH body, the confirmation, Save disabled again), putting the old role back when saving fails, reloading when the account is gone, creating an account (the trimmed payload, the cleared form, the reload from page 1), the taken-email error, and paging.

jsdom does no layout and can't follow a real navigation, so these tests say nothing about how a page looks or where the browser lands next.

## Polish

- **Favicon.** `favicon.svg` is the glowing ember dot from the logo on the dark background. One SVG covers every size, so there are no PNG variants to keep in sync.
- **404 page.** FastAPI answers an unknown address with `{"detail": "Not Found"}` — fine for an API client, a dead end in a browser. `not_found_handler` in `app/web/routes.py` serves `404.html` (still with status 404) when the request asks for HTML and the path isn't under `/api/` or `/static/`. Everything else, and every status other than 404, goes to FastAPI's normal handler, so API clients see no change.
- **Narrow screens.** Below 640px the brand and nav links shrink and never wrap, the nav button gets smaller padding, and the home page's "How it works" link — an anchor to a section a scroll away — is hidden. Below 360px the gaps tighten once more. Measured on every page, logged in and out: the nav stays on one line with no horizontal scroll at 375px and at 320px.

## Previewing without Docker

`scripts/preview_server.py` serves the real pages and static files and answers `/api/v1` from memory, so the frontend can be clicked through on a machine without Postgres or Redis. Requests are validated by the real schemas in `app/schemas`, responses are built from them too, and questions and scores come from the real `FakeAIProvider` — so status codes, `error_code` values and JSON shapes match the real API. It skips rate limits and the dashboard cache, and forgets everything on restart. `POST /api/v1/dev/reset` wipes it without a restart, and `POST /api/v1/dev/make-admin` with `{"email": "..."}` gives an account the admin role.

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
.venv\Scripts\python scripts/preview_server.py
```

Then open http://127.0.0.1:8765. Anything that depends on the database or Redis — migrations, rate limiting, the backend test suite — still needs `docker compose up`.

## Continuous integration

`.github/workflows/ci.yml` runs three jobs on every push to `main` and every pull request:

| Job | What it checks |
|---|---|
| `test` | black, isort and ruff, then the backend suite against Postgres and Redis service containers, with the coverage gate |
| `frontend` | `npm ci` and `npm test` in `tests-frontend` on Node.js 20, the oldest version `package.json` allows |
| `docker` | builds `docker/Dockerfile`, starts the container without a database (pages and static files don't need one), and checks with `curl` that `/`, `/register`, `/login`, `api.js` and the favicon are served and that an unknown page gets a 404 |

## Progress

- **v1.1** — static file serving + page routing wired into the FastAPI app (`app/web/routes.py`, `StaticFiles` mount in `main.py`, `Dockerfile`/`docker-compose.yml` updated to ship `static/`). Placeholder page only.
- **v1.2** — design system (`style.css`: color tokens, typography, buttons, cards, chips) and the API client (`api.js`: fetch wrapper, token storage, auto-refresh).
- **v1.3** — the real landing page (`home.css`, `nav.js`, `hero.js`, full `index.html`).
- **v1.4** — sign-up: `register.html`, `forms.css`, `auth.css`, `register.js`, the `/register` route, backend page tests and the first frontend tests.
- **v1.5** — log-in: `login.html`, `login.js`, the `/login` route, page and jsdom tests.
- **v1.6** — members-only pages: `guard.js`, placeholder `interview.html`, `history.html`, `dashboard.html`, their routes, page and jsdom tests.
- **v1.7** — starting an interview: `interview.css`, `interview.js`, the start form in `interview.html`, a placeholder `session.html` at `/interview/{id}`, sign-up now lands on `/interview`, page and jsdom tests. Also fixed: on screens under 640px the `.container` rule reset the vertical padding of `.page-section`.
- **v1.8** — the interview session: `session.html`, `session.css`, `session.js`, `heat.js`, jsdom tests. Plus `scripts/preview_server.py` for previewing without Docker.
- **v1.8.1** — `total_questions` in the interview API responses, so the session shows "Question 2 of 5". Also fixed: the session page added 1 to `order_index`, which the API already counts from 1, so the first question showed as "Question 2".
- **v1.9** — history: `history.html`, `history.css`, `history.js`, jsdom tests; the score meter moved to `score.css` and `paintScore` to `heat.js`.
- **v1.10** — dashboard: `dashboard.html`, `dashboard.css`, `dashboard.js`, jsdom tests.
- **v1.11** — polish and CI: favicon, 404 page, a nav that fits phone screens, `frontend` and `docker` CI jobs, README brought up to date.
- **v1.12** — admin: the `/admin` page (`admin.html`, `admin.css`, `admin.js`), `api.patch`, the admin endpoints in the preview server, page and jsdom tests. Built on the backend's `role` column and `/admin` endpoints.

## What's next

- An "Admin" nav link that shows only for admins. Every page would need the role, so it means one more `GET /profile/me` per page or putting the role in the token.
- Static files have no cache-busting. After a deploy, a browser can keep running an old `api.js` next to a new page script (seen while building the admin page: the cached `api.js` had no `patch`). Versioned file names or `Cache-Control: no-cache` would fix it.
- `.pagination { display: flex }` in `history.css` overrides the `hidden` attribute, so the history page shows "Page 1 of 1" with disabled buttons when everything fits on one page. `admin.css` has a `[hidden]` rule for this; history needs the same.
