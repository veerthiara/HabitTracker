"""Search service — thin helper for embedding a user query.

The API layer delegates query embedding here so it depends only on the
EmbeddingProvider abstraction rather than a concrete implementation.
"""

from habittracker.providers.base import EmbeddingProvider


def embed_query(provider: EmbeddingProvider, text: str) -> list[float]:
    """Embed a search query string and return the vector.

    Args:
        provider: Any :class:`EmbeddingProvider` implementation.
        text:     The raw query text from the user.

    Returns:
        A list of floats (the embedding vector) ready for pgvector search.

    Raises:
        EmbeddingError: if the provider fails to produce a vector.
    """
    return provider.embed(text)
