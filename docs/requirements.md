# SkillForge AI — Requirements

Requirements are grouped by module. Each functional requirement has a user story ("As a [role], I want [capability], so that [benefit]") plus acceptance criteria.

## 1. Functional Requirements

### 1.1 Authentication

**FR-1.1 Register**
As a new user, I want to create an account with email and password, so that I can save my interview history.
- Email must be unique and a valid format.
- Password minimum 8 characters, at least one letter and one digit.
- Password is stored hashed (bcrypt/argon2), never in plaintext.
- Duplicate email returns `409` with a clear error, not a generic `400`.

**FR-1.2 Login**
As a registered user, I want to log in with email and password, so that I get an access token to use the API.
- Returns an access token (short-lived) and a refresh token (long-lived) on success.
- Wrong password/email returns a generic "invalid credentials" message (no hint about which field is wrong, to avoid user enumeration).
- Failed login attempts are rate-limited per IP and per account.

**FR-1.3 Refresh**
As a logged-in user, I want my session to renew without re-entering my password, so that I'm not logged out every 20 minutes.
- Refresh token exchanges for a new access token.
- Refresh tokens are single-use and rotate on each refresh (the old one is revoked).
- Expired or revoked refresh tokens are rejected with `401`.

**FR-1.4 Logout**
As a logged-in user, I want to log out, so that my refresh token can no longer be used from a stolen device.
- Logout revokes the refresh token server-side (not just deleted client-side).

### 1.2 Profile

**FR-2.1 View profile** — logged-in user sees name, email, account creation date.

**FR-2.2 Edit profile** — logged-in user can update display name. Email is not editable in v1 (avoids re-verification flow complexity).

### 1.3 Interview

**FR-3.1 Start interview**
As a user, I want to start an interview by choosing a language and difficulty, so that I get relevant questions.
- Language ∈ {python, java, cpp, javascript}. Difficulty ∈ {junior, middle, senior}.
- Starting an interview immediately returns the first question — no separate "fetch first question" call.
- A user can have at most one `in_progress` interview at a time (must finish or abandon before starting another) — keeps state simple for v1.

**FR-3.2 Answer a question**
As a user in an active interview, I want to submit a free-text answer, so that I get feedback and move forward.
- The answer is evaluated for correctness, completeness, and clarity.
- Response includes a numeric score (0–10) for that answer and short written feedback.
- If more questions remain, the next question is included in the same response (no extra round trip).
- If that was the last question, the interview is marked `completed` and an overall score is computed.

**FR-3.3 Finish / abandon interview**
As a user, I want to end an interview early, so that I'm not stuck if I run out of time.
- Ending early marks the interview `completed` with a score computed from answered questions only.

### 1.4 History

**FR-4.1 List past interviews** — paginated list with language, difficulty, score, date.

**FR-4.2 View interview detail** — every question, the user's answer, and the feedback for a specific past interview.

### 1.5 Dashboard

**FR-5.1 Aggregate stats**
As a user, I want to see total interviews taken, my average score, and my best/weakest topics, so that I know what to study next.
- "Topic" is derived from the question's `topic` field (see database.md).
- A topic needs at least 2 scored data points before it's surfaced in best/weak lists, to avoid one answer skewing the label.

## 2. Non-Functional Requirements

### 2.1 Security
- Passwords hashed with bcrypt (or argon2id); never logged, never returned in any API response.
- JWT access tokens are short-lived (15–30 min); refresh tokens are long-lived (7–30 days), stored server-side as a hash, and revocable.
- All write endpoints validate input via Pydantic schemas; no raw SQL string interpolation anywhere.
- Auth endpoints are rate-limited to blunt credential-stuffing and brute-force attempts.
- CORS restricted to known frontend origins, not `*`.

### 2.2 Performance
- All I/O (DB, cache, AI provider calls) is async; no blocking calls in request handlers.
- P95 latency target: < 300 ms for DB-only endpoints, < 8 s for AI-evaluation endpoints (dominated by the LLM call itself).
- Dashboard stats are cached in Redis with a short TTL and invalidated on interview completion.

### 2.3 Reliability
- AI provider calls have a timeout and a bounded number of retries with backoff; a failed AI call returns a clear error instead of hanging.
- The service degrades gracefully if Redis is unavailable (cache is an optimization, not a hard dependency for correctness).

### 2.4 Scalability
- The API is stateless (no in-memory session state) so it can run as multiple replicas without sticky sessions.
- Database access goes through a connection pool sized for the deployment target.

### 2.5 Observability
- Structured (JSON) logs with a request/correlation ID present on every log line for a given request.
- `/health` checks DB and Redis connectivity, not just "process is running."

### 2.6 Testability
- Every service-layer method has unit tests with the repository layer mocked.
- Core flows (register → login → start interview → answer → finish) have integration tests against a real test database in CI.
- Target: 80%+ line coverage on `app/services` and `app/api`, enforced in CI.
