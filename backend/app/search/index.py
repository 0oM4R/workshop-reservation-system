"""Rank workshops in memory by keyword, semantic or hybrid search."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

RESULT_LIMIT = 10
WORKSHOP_ID = "workshop_id"


class SearchMode(StrEnum):
    """How workshops are ranked against a query."""

    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class SearchDocument:
    """Searchable text of one workshop."""

    workshop_id: int
    title: str
    description: str

    @property
    def text(self) -> str:
        """Join title and description."""
        return f"{self.title}. {self.description}"

    def as_document(self) -> Document:
        """Wrap the text for LangChain, keeping the workshop ID in metadata."""
        return Document(
            page_content=self.text,
            metadata={WORKSHOP_ID: self.workshop_id},
        )


def workshop_ids_of(documents: list[Document]) -> list[int]:
    """Return each document's workshop ID, in order."""
    workshop_ids: list[int] = []
    for document in documents:
        workshop_id = document.metadata[WORKSHOP_ID]
        workshop_ids.append(workshop_id)
    return workshop_ids


class SearchIndex:
    """Search workshops by keyword, by meaning, or both."""

    def __init__(
        self, documents: Sequence[SearchDocument], embeddings: Embeddings
    ) -> None:
        """Build both retrievers; blocks while embedding."""
        raise NotImplementedError

    async def search(self, query: str, mode: SearchMode) -> list[int]:
        """Return matching workshop IDs, best first."""
        raise NotImplementedError
