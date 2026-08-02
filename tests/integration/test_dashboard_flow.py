from tests.conftest import register_and_login


async def _complete_interview_with_one_answer(client, headers, language, difficulty, answer):
    start = await client.post(
        "/api/v1/interviews", json={"language": language, "difficulty": difficulty}, headers=headers
    )
    interview_id = start.json()["id"]
    question_id = start.json()["current_question"]["id"]
    await client.post(
        f"/api/v1/interviews/{interview_id}/answer",
        json={"question_id": question_id, "answer": answer},
        headers=headers,
    )
    await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)


async def test_dashboard_stats_reflect_real_interview_data(client):
    headers = await register_and_login(client, "dashboard@example.com")

    empty_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert empty_resp.status_code == 200
    empty_body = empty_resp.json()
    assert empty_body["total_interviews"] == 0
    assert empty_body["average_score"] is None
    assert empty_body["best_topics"] == []

    # FakeAIProvider always opens a fresh interview with the same first
    # topic for a given language, so two single-question interviews here
    # both land on the same topic - exactly two data points, the minimum
    # FR-5.1 needs for it to be surfaced.
    good_answer = "A thorough, detailed answer that explains the reasoning and tradeoffs at length."
    for _ in range(2):
        await _complete_interview_with_one_answer(client, headers, "python", "junior", good_answer)

    stats_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert stats_resp.status_code == 200
    body = stats_resp.json()
    assert body["total_interviews"] == 2
    assert body["average_score"] is not None
    assert len(body["best_topics"]) >= 1


async def test_dashboard_cache_invalidates_on_interview_completion(client):
    headers = await register_and_login(client, "cacheinvalidate@example.com")

    first_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert first_resp.json()["total_interviews"] == 0

    await _complete_interview_with_one_answer(client, headers, "python", "junior", "a short answer")

    second_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    assert second_resp.json()["total_interviews"] == 1


async def test_topics_need_at_least_two_data_points_to_appear(client):
    headers = await register_and_login(client, "onedatapoint@example.com")

    await _complete_interview_with_one_answer(
        client, headers, "python", "junior", "one answer only"
    )

    stats_resp = await client.get("/api/v1/dashboard/stats", headers=headers)
    body = stats_resp.json()
    assert body["best_topics"] == []
    assert body["weak_topics"] == []


async def test_dashboard_requires_authentication(client):
    resp = await client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 401
