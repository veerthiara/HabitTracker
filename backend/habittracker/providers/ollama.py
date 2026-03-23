"""Ollama embedding provider.

Calls the local Ollama server's /api/embeddings endpoint.
Configuration is read from habittracker.core.config — no hardcoded values here.

Retries:
    Transient HTTP failures are retried up to OLLAMA_MAX_RETRIES times with
    exponential backoff starting at OLLAMA_RETRY_BACKOFF_SEC seconds.
"""

import logging
import time

import httpx

from habittracker.core.config import (
    EMBED_EXPECTED_DIMS,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    OLLAMA_MAX_RETRIES,
    OLLAMA_RETRY_BACKOFF_SEC,
    OLLAMA_TIMEOUT_SEC,
)
from habittracker.providers.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)


class OllamaProvider(EmbeddingProvider):
    """Embedding provider backed by a local Ollama server."""

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_EMBED_MODEL,
        timeout: float = OLLAMA_TIMEOUT_SEC,
        max_retries: int = OLLAMA_MAX_RETRIES,
        retry_backoff: float = OLLAMA_RETRY_BACKOFF_SEC,
        expected_dims: int = EMBED_EXPECTED_DIMS,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._expected_dims = expected_dims
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._client = httpx.Client(timeout=timeout)

    @property
    def dimensions(self) -> int:
        return self._expected_dims

    def embed(self, text: str) -> list[float]:
        """Call Ollama and return the embedding vector.

        Retries on transient HTTP errors (5xx, connect errors) up to
        max_retries times with exponential backoff.

        Raises:
            EmbeddingError: on non-retryable failure or exhausted retries.
        """
        payload = {"model": self._model, "prompt": text}
        last_exc: Exception | None = None

        for attempt in range(self._max_retries + 1):
            try:
                resp = self._client.post(
                    f"{self._base_url}/api/embeddings", json=payload
                )
                resp.raise_for_status()
                data = resp.json()

                if "embedding" not in data:
                    raise EmbeddingError(
                        f"Ollama response missing 'embedding' key: {data}"
                    )

                vector: list[float] = data["embedding"]
                logger.debug(
                    "Ollama embed OK (model=%s, dims=%d)", self._model, len(vector)
                )
                return vector

            except httpx.HTTPStatusError as exc:
                # 4xx errors are not retryable.
                if exc.response.status_code < 500:
                    raise EmbeddingError(
                        f"Ollama returned {exc.response.status_code}: {exc.response.text}"
                    ) from exc
                last_exc = exc
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_exc = exc

            if attempt < self._max_retries:
                wait = self._retry_backoff * (2**attempt)
                logger.warning(
                    "Ollama request failed (attempt %d/%d), retrying in %.1fs — %s",
                    attempt + 1,
                    self._max_retries + 1,
                    wait,
                    last_exc,
                )
                time.sleep(wait)

        raise EmbeddingError(
            f"Ollama embed failed after {self._max_retries + 1} attempt(s): {last_exc}"
        ) from last_exc
