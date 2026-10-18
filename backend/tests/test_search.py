"""Tests for the workshop search building blocks."""

from langchain_core.documents import Document

from app.search.index import (
    SearchDocument,
    build_keyword_retriever,
    tokenize,
    workshop_ids_of,
)

SOURDOUGH = SearchDocument(
    1, "Sourdough Baking", "Bake a loaf of sourdough bread from your own starter."
)
PASTRY = SearchDocument(2, "Pastry Basics", "Bake bread rolls and croissants.")
BIKES = SearchDocument(3, "Bike Repair", "Fix a flat tire and adjust the brakes.")
QUERY = "sourdough bread"


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


def test_tokenize_lowercases_drops_stop_words_and_stems() -> None:
    """Punctuation splits; "for" and "on" drop; plurals and -ing stem."""
    assert tokenize("Shipping the APIs, hands-on for Beginners!") == [
        "ship",
        "api",
        "hand",
        "beginn",
    ]


def test_keyword_retriever_returns_only_workshops_sharing_a_word() -> None:
    """Both terms beat one; Bikes shares neither and is left out."""
    retriever = build_keyword_retriever(documents_of([SOURDOUGH, PASTRY, BIKES]))

    assert retriever is not None
    assert workshop_ids_of(retriever.invoke(QUERY)) == [1, 2]


def test_keyword_retriever_needs_a_searchable_word() -> None:
    """No workshops, or only stop words: BM25 has nothing to index."""
    stop_words_only = documents_of([SearchDocument(1, "The", "and")])

    assert build_keyword_retriever([]) is None
    assert build_keyword_retriever(stop_words_only) is None
