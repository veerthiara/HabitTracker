"""Abstract base class for embedding providers.

Any embedding backend (Ollama, OpenAI, HuggingFace, etc.) must implement
this interface. The pipeline (service.py) depends only on this abstraction,
making providers fully swappable without touching any other code.
"""

from abc import ABC, abstractmethod


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
