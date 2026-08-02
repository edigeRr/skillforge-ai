"""Basic load test for Sprint 5, SF-77: fire concurrent answer requests at a
running instance and report latency stats. Not part of the automated test
suite - point it at a real running server (docker compose or local uvicorn).

Setup (register + log in one user per worker) happens sequentially and
retries on 429, because /auth/register and /auth/login share a tight
rate-limit budget (SF-76: 5 requests/minute per IP - the classic
brute-force/credential-stuffing target, so it stays strict even for a
friendly load-testing script). The default concurrency=2 needs 4 auth
calls, safely under that budget, so setup should be immediate. Note that
this is a *fixed*-window limiter (see rate_limit.py): once you go over the
limit, retrying doesn't help you escape faster - it just polls until the
window itself rolls over - so concurrency > 2 can mean up to ~60s of
"rate limited, waiting" during setup. That's the limiter doing its job,
not a bug in this script. The actual load test - concurrent POST
/interviews/{id}/answer - runs against the much wider
general_write_rate_limit (30/minute per IP), so it isn't affected.

Usage:
    docker compose up -d
    python scripts/load_test.py --concurrency 2 --requests-per-worker 8
"""

import argparse
import asyncio
import statistics
import time
import uuid

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
PASSWORD = "Str0ngPass1"


async def _post_with_429_retry(
    client: httpx.AsyncClient, path: str, json: dict, *, max_wait_seconds: float = 90.0
) -> httpx.Response:
    deadline = time.monotonic() + max_wait_seconds
    while True:
        response = await client.post(path, json=json)
        if response.status_code != 429:
            return response
        if time.monotonic() >= deadline:
            return response
        print(f"  rate limited on {path}, waiting 5s...")
        await asyncio.sleep(5)


async def _register_and_login(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    await _post_with_429_retry(
        client, "/api/v1/auth/register", {"email": email, "password": PASSWORD, "name": "Load Test"}
    )
    login = await _post_with_429_retry(
        client, "/api/v1/auth/login", {"email": email, "password": PASSWORD}
    )
    login.raise_for_status()
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _start_interview(client: httpx.AsyncClient, headers: dict[str, str]) -> tuple[str, str]:
    start = await client.post(
        "/api/v1/interviews", json={"language": "python", "difficulty": "junior"}, headers=headers
    )
    start.raise_for_status()
    body = start.json()
    return body["id"], body["current_question"]["id"]


async def worker(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    requests_per_worker: int,
    latencies: list[float],
) -> None:
    interview_id, question_id = await _start_interview(client, headers)

    for _ in range(requests_per_worker):
        start_time = time.monotonic()
        resp = await client.post(
            f"/api/v1/interviews/{interview_id}/answer",
            json={
                "question_id": question_id,
                "answer": "A brief answer for load testing purposes.",
            },
            headers=headers,
        )
        latencies.append((time.monotonic() - start_time) * 1000)

        if resp.status_code != 200:
            break  # this worker's session broke (e.g. rate limited) - stop rather than skew results

        body = resp.json()
        if body["next_question"]:
            question_id = body["next_question"]["id"]
        else:
            interview_id, question_id = await _start_interview(client, headers)


async def main(base_url: str, concurrency: int, requests_per_worker: int) -> None:
    latencies: list[float] = []
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            await client.get("/health")
        except httpx.ConnectError:
            print(f"Could not reach {base_url} - is the server running?")
            return

        print(f"Setting up {concurrency} sessions (sequential, respects the auth rate limit)...")
        sessions = [
            await _register_and_login(client, f"loadtest-{i}-{uuid.uuid4().hex[:8]}@example.com")
            for i in range(concurrency)
        ]

        print("Running load test...")
        await asyncio.gather(
            *[worker(client, headers, requests_per_worker, latencies) for headers in sessions]
        )

    if not latencies:
        print("No successful requests completed.")
        return

    latencies.sort()
    total = len(latencies)
    p95_index = min(total - 1, int(total * 0.95))
    print(f"POST /interviews/{{id}}/answer - {total} requests, concurrency={concurrency}")
    print(f"  min: {latencies[0]:.0f} ms")
    print(f"  p50: {statistics.median(latencies):.0f} ms")
    print(f"  p95: {latencies[p95_index]:.0f} ms")
    print(f"  max: {latencies[-1]:.0f} ms")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Basic load test for POST /interviews/{id}/answer")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--concurrency", type=int, default=2, help="number of concurrent virtual users"
    )
    parser.add_argument("--requests-per-worker", type=int, default=8)
    args = parser.parse_args()
    asyncio.run(main(args.base_url, args.concurrency, args.requests_per_worker))
