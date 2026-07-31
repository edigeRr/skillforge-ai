import httpx

from app.ai.retrying_provider import RetryingJSONProvider
from app.core.config import get_settings

settings = get_settings()

ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-3-5-haiku-20241022"


class AnthropicProvider(RetryingJSONProvider):
    provider_name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 15.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else settings.ANTHROPIC_API_KEY
        if not resolved_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self._model = model
        client = client or httpx.AsyncClient(
            base_url="https://api.anthropic.com",
            headers={
                "x-api-key": resolved_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json",
            },
            timeout=timeout,
        )
        super().__init__(client=client, max_retries=max_retries)

    async def _request_json(self, system: str, user_message: str) -> dict:
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "system": system,
            "messages": [{"role": "user", "content": user_message}],
        }
        response = await self._post_with_retry("/v1/messages", payload, model=self._model)
        body = response.json()
        text = "".join(
            block.get("text", "")
            for block in body.get("content", [])
            if block.get("type") == "text"
        )
        return self._extract_json(text)
