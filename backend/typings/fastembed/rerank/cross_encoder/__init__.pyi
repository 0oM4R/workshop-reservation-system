"""Type the reranker API used by workshop search.

fastembed marks its own types as partial, and pyright finds none for this module.
"""

from collections.abc import Iterable

class TextCrossEncoder:
    """Score query and document pairs with a local cross-encoder model."""

    def __init__(self, model_name: str) -> None:
        """Load the model, downloading it unless it is already cached."""
        ...

    def rerank(self, query: str, documents: Iterable[str]) -> Iterable[float]:
        """Return one relevance score per document, in order."""
        ...
