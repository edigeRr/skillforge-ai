import json

import httpx
import pytest

from app.ai import anthropic_provider, openai_provider
from app.ai.anthropic_provider import AnthropicProvider
from app.ai.openai_provider import OpenAIProvider
from app.ai.retrying_provider import AIProviderError


def _anthropic_body(topic="arrays", question="What is a hash map?") -> dict:
    return {
        "content": [{"type": "text", "text": json.dumps({"topic": topic, "question": question})}],
        "usage": {"input_tokens": 10, "output_tokens": 20},
    }


def _openai_body(topic="arrays", question="What is a hash map?") -> dict:
    return {
        "choices": [{"message": {"content": json.dumps({"topic": topic, "question": question})}}]
    }


def _client_with_handler(base_url: str, handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url=base_url)


# --- Anthropic ---------------------------------------------------------


async def test_anthropic_generate_question_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_anthropic_body())

    client = _client_with_handler("https://api.anthropic.com", handler)
    provider = AnthropicProvider(api_key="test-key", client=client)

    result = await provider.generate_question("python", "junior", [])

    assert result.topic == "arrays"
    assert result.question == "What is a hash map?"
    await provider.aclose()


async def test_anthropic_evaluate_answer_clamps_score_to_valid_range():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "content": [
                {"type": "text", "text": json.dumps({"score": 15, "feedback": "way too generous"})}
            ]
        }
        return httpx.Response(200, json=body)

    client = _client_with_handler("https://api.anthropic.com", handler)
    provider = AnthropicProvider(api_key="test-key", client=client)

    evaluation = await provider.evaluate_answer("some question", "some answer")

    assert evaluation.score == 10.0
    await provider.aclose()


async def test_anthropic_raises_on_malformed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"content": [{"type": "text", "text": "not valid json at all"}]}
        return httpx.Response(200, json=body)

    client = _client_with_handler("https://api.anthropic.com", handler)
    provider = AnthropicProvider(api_key="test-key", client=client)

    with pytest.raises(AIProviderError):
        await provider.generate_question("python", "junior", [])
    await provider.aclose()


async def test_anthropic_retries_on_timeout_then_succeeds(monkeypatch):
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.ai.retrying_provider.asyncio.sleep", no_sleep)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectTimeout("simulated timeout", request=request)
        return httpx.Response(200, json=_anthropic_body())

    client = _client_with_handler("https://api.anthropic.com", handler)
    provider = AnthropicProvider(api_key="test-key", client=client, max_retries=2)

    result = await provider.generate_question("python", "junior", [])

    assert calls["n"] == 2
    assert result.topic == "arrays"
    await provider.aclose()


async def test_anthropic_raises_after_exhausting_retries(monkeypatch):
    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.ai.retrying_provider.asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("simulated timeout", request=request)

    client = _client_with_handler("https://api.anthropic.com", handler)
    provider = AnthropicProvider(api_key="test-key", client=client, max_retries=1)

    with pytest.raises(AIProviderError):
        await provider.generate_question("python", "junior", [])
    await provider.aclose()


def test_anthropic_missing_api_key_raises_at_construction(monkeypatch):
    monkeypatch.setattr(anthropic_provider.settings, "ANTHROPIC_API_KEY", None)

    with pytest.raises(RuntimeError):
        AnthropicProvider()


# --- OpenAI --------------------------------------------------------------


async def test_openai_generate_question_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_openai_body())

    client = _client_with_handler("https://api.openai.com", handler)
    provider = OpenAIProvider(api_key="test-key", client=client)

    result = await provider.generate_question("java", "middle", [])

    assert result.topic == "arrays"
    await provider.aclose()


async def test_openai_evaluate_answer_parses_response():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {"message": {"content": json.dumps({"score": 6.5, "feedback": "decent answer"})}}
            ]
        }
        return httpx.Response(200, json=body)

    client = _client_with_handler("https://api.openai.com", handler)
    provider = OpenAIProvider(api_key="test-key", client=client)

    evaluation = await provider.evaluate_answer("q", "a")

    assert evaluation.score == 6.5
    assert evaluation.feedback == "decent answer"
    await provider.aclose()


async def test_openai_raises_on_malformed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"choices": [{"message": {"content": "nope, not json"}}]}
        return httpx.Response(200, json=body)

    client = _client_with_handler("https://api.openai.com", handler)
    provider = OpenAIProvider(api_key="test-key", client=client)

    with pytest.raises(AIProviderError):
        await provider.generate_question("java", "middle", [])
    await provider.aclose()


def test_openai_missing_api_key_raises_at_construction(monkeypatch):
    monkeypatch.setattr(openai_provider.settings, "OPENAI_API_KEY", None)

    with pytest.raises(RuntimeError):
        OpenAIProvider()
