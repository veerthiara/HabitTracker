"""Abstract base classes for embedding and chat providers.

Any backend (Ollama, OpenAI, HuggingFace, etc.) must implement the
relevant interface. The pipeline and API depend only on these abstractions,
making providers fully swappable without touching any other code.
"""

from abc import ABC, abstractmethod


# ── Embedding ─────────────────────────────────────────────────────────────────

class EmbeddingProvider(ABC):
    """Contract every embedding provider must satisfy."""

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """Return a normalized embedding vector for *text*.

        Args:
            text: The content to embed. Must be non-empty.

        Returns:
            A list of floats representing the embedding vector.

        Raises:
            EmbeddingError: on any provider-side failure.
        """
        ...

    @property
    @abstractmethod
    def dimensions(self) -> int:
        """Expected vector dimensionality for this provider + model."""
        ...


class EmbeddingError(RuntimeError):
    """Raised when an embedding provider fails to produce a vector."""


# ── Chat / completion ─────────────────────────────────────────────────────────

class ChatProvider(ABC):
    """Contract every chat/completion provider must satisfy."""

    @abstractmethod
    def complete(self, messages: list[dict]) -> str:
        """Generate a completion from an ordered list of chat messages.

        Each message is a dict with keys:
            role:    "system", "user", or "assistant".
            content: The text content for that role.

        The caller is responsible for ordering the messages correctly
        (system first, then conversation history, then current user turn).

        Args:
            messages: Ordered list of role/content dicts.

        Returns:
            The model's response as a plain string.

        Raises:
            ChatCompletionError: on any provider-side failure or timeout.
        """
        ...


class ChatCompletionError(RuntimeError):
    """Raised when a chat provider fails to produce a completion."""
