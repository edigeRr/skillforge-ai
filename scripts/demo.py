"""Demo walkthrough for Sprint 6, SF-84: a substitute for a recorded demo
GIF/video (this environment can't record video) - run this against a live
server and screen-record *this*, or just read the output to see the whole
product loop in one place. Uses AI_PROVIDER=fake by default, so it needs
no API key; point it at a real provider for a more convincing recording.

Usage:
    docker compose up -d
    python scripts/demo.py
"""

import argparse
import asyncio
import time
import uuid

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


async def _post_with_429_retry(
    client: httpx.AsyncClient, path: str, json: dict, *, max_wait_seconds: float = 90.0
) -> httpx.Response:
    """Auth endpoints share a tight rate-limit budget (SF-76: 5/min/IP,
    deliberately strict since they're the classic brute-force target).
    Running this demo repeatedly in quick succession can bump into that -
    wait it out rather than crash with a confusing KeyError."""
    deadline = time.monotonic() + max_wait_seconds
    while True:
        response = await client.post(path, json=json)
        if response.status_code != 429:
            return response
        if time.monotonic() >= deadline:
            return response
        print(f"  (rate limited on {path}, waiting 5s - this is expected if you just ran this)")
        await asyncio.sleep(5)


def step(text: str, pause: float) -> None:
    print(f"\n>>> {text}")
    time.sleep(pause)


def show(label: str, payload: object, pause: float) -> None:
    print(f"{label}: {payload}")
    time.sleep(pause)


async def main(base_url: str, pause: float) -> None:
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
        try:
            await client.get("/health")
        except httpx.ConnectError:
            print(f"Could not reach {base_url} - is the server running? (docker compose up)")
            return

        email = f"demo-{uuid.uuid4().hex[:8]}@example.com"

        step(f"Registering {email}...", pause)
        register = await _post_with_429_retry(
            client,
            "/api/v1/auth/register",
            {"email": email, "password": "Str0ngPass1", "name": "Demo User"},
        )
        show("Registered", register.json(), pause)

        step("Logging in...", pause)
        login = await _post_with_429_retry(
            client, "/api/v1/auth/login", {"email": email, "password": "Str0ngPass1"}
        )
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        print("Got an access token.")
        time.sleep(pause)

        step("Starting a Python / middle interview...", pause)
        start = await client.post(
            "/api/v1/interviews",
            json={"language": "python", "difficulty": "middle"},
            headers=headers,
        )
        interview = start.json()
        interview_id = interview["id"]
        question = interview["current_question"]
        show("Question 1", question["question"], pause)

        answers = [
            "I'd walk the list once and use a set to track items I've already "
            "seen, appending to a new output list only the first time each "
            "value shows up. That preserves the original order, unlike sorting "
            "or converting straight to a set, and it's O(n) time with O(n) "
            "extra space for the seen-set and the output list.",
            "The GIL is a single lock around the Python interpreter that lets "
            "only one thread execute Python bytecode at a time, even on a "
            "multi-core machine. For CPU-bound work that means extra threads "
            "don't actually add parallelism - the fix is either the "
            "multiprocessing module, which sidesteps the GIL with separate "
            "processes, or offloading the hot loop into a C extension or "
            "library like NumPy that releases the GIL while it runs.",
        ]

        question_id = question["id"]
        for i, answer_text in enumerate(answers, start=1):
            step(f"Answering question {i}...", pause)
            show("Answer", answer_text, pause)
            resp = await client.post(
                f"/api/v1/interviews/{interview_id}/answer",
                json={"question_id": question_id, "answer": answer_text},
                headers=headers,
            )
            body = resp.json()
            show("Score", f"{body['score']}/10", pause)
            show("Feedback", body["feedback"], pause)
            if body["next_question"]:
                question_id = body["next_question"]["id"]
                show("Next question", body["next_question"]["question"], pause)
            else:
                print("Interview completed.")

        step("Ending the interview early to see the summary...", pause)
        finish = await client.post(f"/api/v1/interviews/{interview_id}/finish", headers=headers)
        finished = finish.json()
        show("Final status", finished["status"], pause)
        show("Overall score", finished["score"], pause)

        step("Checking the dashboard...", pause)
        stats = await client.get("/api/v1/dashboard/stats", headers=headers)
        show("Dashboard", stats.json(), pause)

        print("\nDone - that's the full product loop, start to finish.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scripted walkthrough of the full interview flow")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--pause", type=float, default=1.0, help="seconds to pause between steps (for recording)"
    )
    args = parser.parse_args()
    asyncio.run(main(args.base_url, args.pause))
