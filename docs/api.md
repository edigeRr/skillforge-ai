# SkillForge AI — API Specification

Base path: `/api/v1`. All request/response bodies are JSON. All timestamps are ISO 8601 UTC.

## 1. Authentication

All endpoints except `/auth/register`, `/auth/login`, `/auth/refresh`, and `/health` require an `Authorization: Bearer <access_token>` header.

## 2. Conventions

**Error envelope** (all 4xx/5xx responses):
```json
{
  "detail": "Human-readable message",
  "error_code": "INVALID_CREDENTIALS"
}
```

**Pagination** (list endpoints): query params `page` (default 1) and `page_size` (default 20, max 100). Response wraps results:
```json
{
  "items": [...],
  "page": 1,
  "page_size": 20,
  "total": 47
}
```

**Interactive docs**: FastAPI auto-generates a live OpenAPI/Swagger UI at `/docs` and a raw spec at `/openapi.json` directly from the route definitions and Pydantic schemas below — this file is the source of truth for what those routes should do, not a hand-maintained duplicate of the generated spec.

## 3. Auth

### POST /auth/register
Request:
```json
{ "email": "user@example.com", "password": "Str0ngPass!", "name": "Jane Doe" }
```
Response `201`:
```json
{ "id": "uuid", "email": "user@example.com", "name": "Jane Doe", "created_at": "2026-01-01T00:00:00Z" }
```
Errors: `409 EMAIL_ALREADY_EXISTS`, `422` (validation).

### POST /auth/login
Response `200`:
```json
{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 1800 }
```
Errors: `401 INVALID_CREDENTIALS`, `429 TOO_MANY_ATTEMPTS`.

### POST /auth/refresh
Request: `{ "refresh_token": "..." }`
Response `200`: same shape as login (new access token + rotated refresh token).
Errors: `401 INVALID_REFRESH_TOKEN` (expired, revoked, or unknown).

### POST /auth/logout
Requires auth. Request: `{ "refresh_token": "..." }`. Revokes it server-side. Response `204`.

## 4. Profile

### GET /profile/me
Response `200`: `{ "id": "uuid", "email": "user@example.com", "name": "Jane Doe", "created_at": "..." }`

### PUT /profile/me
Request: `{ "name": "New Name" }`. Response `200`: updated profile object.

## 5. Interview

### POST /interviews
Request:
```json
{ "language": "python", "difficulty": "middle" }
```
Response `201`:
```json
{
  "id": "uuid",
  "language": "python",
  "difficulty": "middle",
  "status": "in_progress",
  "current_question": { "id": "uuid", "order_index": 1, "topic": "arrays", "question": "..." }
}
```
Errors: `409 INTERVIEW_ALREADY_IN_PROGRESS`.

### POST /interviews/{id}/answer
Request:
```json
{ "question_id": "uuid", "answer": "My answer text..." }
```
Response `200`:
```json
{
  "feedback": "Correct on the core approach, but you didn't handle the empty-input case.",
  "score": 7.5,
  "next_question": { "id": "uuid", "order_index": 2, "topic": "recursion", "question": "..." },
  "interview_status": "in_progress"
}
```
When there is no next question, `next_question` is `null` and `interview_status` is `"completed"`.
Errors: `404` (interview/question not found or not owned by caller), `409 QUESTION_ALREADY_ANSWERED`, `409 INTERVIEW_NOT_IN_PROGRESS`.

### POST /interviews/{id}/finish
Ends the interview early. Response `200`: full interview object with `score` computed from answered questions only.

### GET /interviews/{id}
Full interview detail: all questions, answers, feedback, per-question scores, overall score.

## 6. History

### GET /interviews
Paginated list of the caller's past interviews. Optional filters: `language`, `difficulty`, `status`.
Response `200`: paginated envelope of `{ id, language, difficulty, status, score, created_at, finished_at }`.

## 7. Dashboard

### GET /dashboard/stats
Response `200`:
```json
{
  "total_interviews": 12,
  "average_score": 6.8,
  "best_topics": [{ "topic": "arrays", "average_score": 8.9 }],
  "weak_topics": [{ "topic": "concurrency", "average_score": 3.2 }]
}
```
Topics need at least 2 scored data points to appear (see requirements.md, FR-5.1).

## 8. Health

### GET /health
No auth required. Checks DB and Redis connectivity.
Response `200`: `{ "status": "ok", "db": "ok", "redis": "ok" }`. Returns `503` if any dependency check fails.

## 9. Example OpenAPI Fragment

The full spec is auto-generated, but here's the shape for one endpoint as a reference for how the Pydantic schemas should map to it:

```yaml
/api/v1/interviews/{id}/answer:
  post:
    summary: Submit an answer to the current question
    security:
      - bearerAuth: []
    requestBody:
      content:
        application/json:
          schema:
            type: object
            required: [question_id, answer]
            properties:
              question_id: { type: string, format: uuid }
              answer: { type: string, minLength: 1 }
    responses:
      '200':
        description: Answer evaluated
        content:
          application/json:
            schema:
              type: object
              properties:
                feedback: { type: string }
                score: { type: number }
                next_question: { $ref: '#/components/schemas/Question', nullable: true }
                interview_status: { type: string, enum: [in_progress, completed] }
```
