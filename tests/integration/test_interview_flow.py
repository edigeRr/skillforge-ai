from app.core.config import get_settings

settings = get_settings()


async def _register_and_login(client, email: str) -> dict[str, str]:
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Str0ngPass1", "name": "Test User"},
    )
    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Str0ngPass1"}
    )
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def test_full_interview_lifecycle(client):
    headers = await _register_and_login(client, "interviewer@example.com")

    start_resp = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    assert start_resp.status_code == 201
    interview = start_resp.json()
    assert interview["status"] == "in_progress"
    assert interview["current_question"]["order_index"] == 1

    interview_id = interview["id"]
    question_id = interview["current_question"]["id"]
    question_count = settings.INTERVIEW_QUESTION_COUNT

    for i in range(question_count):
        answer_resp = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={
                "question_id": question_id,
                "answer": "A reasonably detailed answer explaining the tradeoffs involved.",
            },
            headers=headers,
        )
        assert answer_resp.status_code == 200
        body = answer_resp.json()
        assert 0 <= body["score"] <= 10

        if i < question_count - 1:
            assert body["interview_status"] == "in_progress"
            assert body["next_question"] is not None
            question_id = body["next_question"]["id"]
        else:
            assert body["interview_status"] == "completed"
            assert body["next_question"] is None

    detail_resp = await client.get(f"/api/v1/interviews/{interview_id}", headers=headers)
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["status"] == "completed"
    assert detail["score"] is not None
    assert len(detail["questions"]) == question_count
    assert all(q["answer"] is not None for q in detail["questions"])


async def test_start_rejects_second_active_interview(client):
    headers = await _register_and_login(client, "twice@example.com")
    first = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/interviews", json={"language": "java", "difficulty": "middle"}, headers=headers
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "INTERVIEW_ALREADY_IN_PROGRESS"


async def test_answer_rejects_non_owner(client):
    owner_headers = await _register_and_login(client, "owner@example.com")
    other_headers = await _register_and_login(client, "other@example.com")

    start = await client.post(
        "/api/v1/interviews",
        json={"language": "python", "difficulty": "junior"},
        headers=owner_headers,
    )
    interview_id = start.json()["id"]
    question_id = start.json()["current_question"]["id"]

    resp = await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        json={"question_id": question_id, "answer": "trying to answer someone else's interview"},
        headers=other_headers,
    )
    assert resp.status_code == 404


async def test_answer_rejects_already_answered_question(client):
    headers = await _register_and_login(client, "reanswer@example.com")
    start = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    interview_id = start.json()["id"]
    question_id = start.json()["current_question"]["id"]

    first = await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        json={"question_id": question_id, "answer": "first answer"},
        headers=headers,
    )
    assert first.status_code == 200

    second = await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        json={"question_id": question_id, "answer": "trying again"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "QUESTION_ALREADY_ANSWERED"


async def test_finish_early_computes_partial_score(client):
    headers = await _register_and_login(client, "early@example.com")
    start = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    interview_id = start.json()["id"]
    question_id = start.json()["current_question"]["id"]

    await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        json={"question_id": question_id, "answer": "a single answer before quitting early"},
        headers=headers,
    )

    finish_resp = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
    assert finish_resp.status_code == 200
    body = finish_resp.json()
    assert body["status"] == "completed"
    assert body["score"] is not None
    answered = [q for q in body["questions"] if q["answer"] is not None]
    assert len(answered) == 1


async def test_finish_rejects_when_already_completed(client):
    headers = await _register_and_login(client, "doublefinish@example.com")
    start = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    interview_id = start.json()["id"]

    first = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
    assert first.status_code == 200

    second = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
    assert second.status_code == 409
    assert second.json()["error_code"] == "INTERVIEW_NOT_IN_PROGRESS"


async def test_history_is_paginated_and_filterable(client):
    headers = await _register_and_login(client, "history@example.com")

    start1 = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    await client.post(f"/api/v1/interviews/{start1.json()['id']}/finish", headers=headers)

    start2 = await client.post(
        "/api/v1/interviews", json={"language": "java", "difficulty": "middle"}, headers=headers
    )
    await client.post(f"/api/v1/interviews/{start2.json()['id']}/finish", headers=headers)

    all_resp = await client.get("/api/v1/interviews", headers=headers)
    assert all_resp.status_code == 200
    assert all_resp.json()["total"] == 2

    filtered_resp = await client.get("/api/v1/interviews?language=java", headers=headers)
    assert filtered_resp.json()["total"] == 1
    assert filtered_resp.json()["items"][0]["language"] == "java"
