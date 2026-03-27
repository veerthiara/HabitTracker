"""Ollama chat/completion provider.

Calls the local Ollama server's /api/chat endpoint.
Configuration is read from habittracker.core.config — no hardcoded values here.

Retries:
    Transient HTTP failures (5xx, connect errors) are retried up to
    OLLAMA_MAX_RETRIES times with exponential backoff.

Timeout:
    If the request exceeds OLLAMA_CHAT_TIMEOUT_SEC, a ChatCompletionError
    is raised immediately — local LLMs can hang on long prompts.
"""

import logging
import time

import httpx

from habittracker.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_CHAT_MODEL,
    OLLAMA_CHAT_TIMEOUT_SEC,
    OLLAMA_MAX_RETRIES,
    OLLAMA_RETRY_BACKOFF_SEC,
)
from habittracker.providers.base import ChatCompletionError, ChatProvider

logger = logging.getLogger(__name__)


class OllamaChatProvider(ChatProvider):
    """Chat/completion provider backed by a local Ollama server.

    Uses the /api/chat endpoint with non-streaming mode so the full
    response is returned in a single HTTP response.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_CHAT_MODEL,
        timeout: float = OLLAMA_CHAT_TIMEOUT_SEC,
        max_retries: int = OLLAMA_MAX_RETRIES,
        retry_backoff: float = OLLAMA_RETRY_BACKOFF_SEC,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._client = httpx.Client(timeout=timeout)

    def complete(self, system: str, user: str) -> str:
        """Send a chat request and return the model's response text.

        Retries on transient HTTP errors (5xx, connect errors) up to
        max_retries times with exponential backoff.

        Args:
            system: System prompt containing instructions / constraints.
            user:   The user's message or question.

        Returns:
            The model's response as a plain string.

        Raises:
            ChatCompletionError: on non-retryable failure, exhausted retries,
                                  timeout, or a malformed response.
        """
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
        }
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.post(
                    f"{self._base_url}/api/chat", json=payload
                )
                resp.raise_for_status()
                data = resp.json()

                try:
                    content = data["message"]["content"]
                except (KeyError, TypeError) as exc:
                    raise ChatCompletionError(
                        f"Ollama chat response missing 'message.content': {data}"
                    ) from exc

                logger.debug(
                    "Ollama chat OK (model=%s, chars=%d)", self._model, len(content)
                )
                return content

            except httpx.HTTPStatusError as exc:
                # 4xx errors are not retryable.
                if exc.response.status_code < 500:
                    raise ChatCompletionError(
                        f"Ollama returned {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                last_exc = exc
            except httpx.TimeoutException as exc:
                raise ChatCompletionError(
                    f"Ollama chat timed out after {self._client.timeout}s"
                ) from exc
            except httpx.ConnectError as exc:
                last_exc = exc

            if attempt < self._max_retries:
                wait = self._retry_backoff * (2**attempt)
                logger.warning(
                    "Ollama chat failed (attempt %d/%d), retrying in %.1fs — %s",
                    attempt + 1,
                    self._max_retries + 1,
                    wait,
                    last_exc,
                )
                time.sleep(wait)

        raise ChatCompletionError(
            f"Ollama chat failed after {self._max_retries + 1} attempt(s): {last_exc}"
        ) from last_exc
