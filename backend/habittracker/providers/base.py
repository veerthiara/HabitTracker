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
    def complete(self, system: str, user: str) -> str:
        """Generate a completion given a system prompt and a user message.

        Args:
            system: Instructions / constraints for the model.
            user:   The user's message or question.

        Returns:
            The model's response as a plain string.

        Raises:
            ChatCompletionError: on any provider-side failure or timeout.
        """
        ...


class ChatCompletionError(RuntimeError):
    """Raised when a chat provider fails to produce a completion."""
