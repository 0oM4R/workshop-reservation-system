"""Tests for the workshop search building blocks."""

from langchain_core.documents import Document

from app.search.index import (
    SearchDocument,
    workshop_ids_of,
)

SOURDOUGH = SearchDocument(
    1, "Sourdough Baking", "Bake a loaf of sourdough bread from your own starter."
)
PASTRY = SearchDocument(2, "Pastry Basics", "Bake bread rolls and croissants.")
BIKES = SearchDocument(3, "Bike Repair", "Fix a flat tire and adjust the brakes.")


def documents_of(workshops: list[SearchDocument]) -> list[Document]:
    """Wrap workshops as LangChain documents, the way the index does."""
    documents: list[Document] = []
    for workshop in workshops:
        documents.append(workshop.as_document())
    return documents


# Building blocks, one layer at a time.


def test_document_text_joins_title_and_description() -> None:
    """Search reads the title and the description as one text."""
    assert SOURDOUGH.as_document().page_content == (
        "Sourdough Baking. Bake a loaf of sourdough bread from your own starter."
    )


def test_documents_keep_workshop_ids_in_order() -> None:
    """Workshop IDs survive the trip through LangChain documents."""
    assert workshop_ids_of(documents_of([BIKES, SOURDOUGH, PASTRY])) == [3, 1, 2]
