import httpx

from app.ai.retrying_provider import RetryingJSONProvider
from app.core.config import get_settings

settings = get_settings()

DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(RetryingJSONProvider):
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 15.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        resolved_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        if not resolved_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self._model = model
        client = client or httpx.AsyncClient(
            base_url="https://api.openai.com",
            headers={"Authorization": f"Bearer {resolved_key}", "content-type": "application/json"},
            timeout=timeout,
        )
        super().__init__(client=client, max_retries=max_retries)

    async def _request_json(self, system: str, user_message: str) -> dict:
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
        }
        response = await self._post_with_retry("/v1/chat/completions", payload, model=self._model)
        body = response.json()
        text = body["choices"][0]["message"]["content"]
        return self._extract_json(text)
