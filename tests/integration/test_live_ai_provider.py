"""Gated integration test - SF-67. Skipped by default so CI never needs a
live API key. Run it yourself once you have one:

    AI_PROVIDER=anthropic ANTHROPIC_API_KEY=sk-... RUN_LIVE_AI_TESTS=1 \\
        pytest tests/integration/test_live_ai_provider.py -v

(or AI_PROVIDER=openai OPENAI_API_KEY=sk-...). This is also a reasonable
starting point for the SF-68 manual QA pass - see scripts/manual_qa.py for
a version that prints results for multiple languages without needing the
full HTTP stack.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_LIVE_AI_TESTS") != "1",
    reason="Set RUN_LIVE_AI_TESTS=1 (and AI_PROVIDER + the matching API key) to hit a real LLM.",
)


async def _register_and_login(client, email: str) -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass1", "name": "Live Test"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Str0ngPass1"}
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


async def test_full_interview_against_a_real_provider(client):
    headers = await _register_and_login(client, "live-ai-test@example.com")

    start = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "middle"}, headers=headers
    )
    assert start.status_code == 201
    question_text = start.json()["current_question"]["question"]
    assert len(question_text) > 10  # a real question, not an empty/placeholder string

    answer_resp = await client.post(
        f"/api/v1/interviews/{start.json()['id']}/answer",
        json={
            "question_id": start.json()["current_question"]["id"],
            "answer": "I would use a hash map to track seen elements, giving O(n) time overall.",
        },
        headers=headers,
    )
    assert answer_resp.status_code == 200
    body = answer_resp.json()
    assert 0 <= body["score"] <= 10
    assert len(body["feedback"]) > 5
