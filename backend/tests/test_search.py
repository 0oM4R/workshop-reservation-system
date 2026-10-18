"""Tests for the workshop search building blocks."""

from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from app.search.index import (
    RESULT_LIMIT,
    SearchDocument,
    build_keyword_retriever,
    build_semantic_retriever,
    tokenize,
    workshop_ids_of,
)

SOURDOUGH = SearchDocument(
    1, "Sourdough Baking", "Bake a loaf of sourdough bread from your own starter."
)
PASTRY = SearchDocument(2, "Pastry Basics", "Bake bread rolls and croissants.")
BIKES = SearchDocument(3, "Bike Repair", "Fix a flat tire and adjust the brakes.")
QUERY = "sourdough bread"
# Chosen so semantic search ranks Pastry, then Bikes, then Sourdough: the
# opposite of keyword search for Sourdough, and Bikes shares no word with QUERY.
VECTORS = {
    QUERY: [1.0, 0.0],
    PASTRY.text: [1.0, 0.0],
    BIKES.text: [1.0, 1.0],
    SOURDOUGH.text: [0.0, 1.0],
}


class LookupEmbeddings(Embeddings):
    """Embeddings read from a table, so semantic ranks are known in advance."""

    def __init__(self, vectors: dict[str, list[float]]) -> None:
        """Embed each text as the vector the table gives it."""
        self.vectors = vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Look up each document's vector."""
        vectors: list[list[float]] = []
        for text in texts:
            vectors.append(self.vectors[text])
        return vectors

    def embed_query(self, text: str) -> list[float]:
        """Look up the query's vector."""
        return self.vectors[text]


def fake_embeddings() -> Embeddings:
    """Random but repeatable vectors, for tests that don't check semantic ranks."""
    return DeterministicFakeEmbedding(size=8)


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


def test_semantic_retriever_returns_closest_vectors_first() -> None:
    """Pastry, Bikes, Sourdough by cosine similarity, shared words or not."""
    documents = documents_of([SOURDOUGH, PASTRY, BIKES])
    retriever = build_semantic_retriever(documents, LookupEmbeddings(VECTORS))

    assert workshop_ids_of(retriever.invoke(QUERY)) == [2, 3, 1]


def test_semantic_retriever_returns_at_most_the_result_limit() -> None:
    """Every workshop has a nearest rank; only the top results come back."""
    workshops: list[SearchDocument] = []
    for number in range(1, RESULT_LIMIT + 5):
        workshops.append(SearchDocument(number, f"Workshop {number}", "Learn."))
    retriever = build_semantic_retriever(documents_of(workshops), fake_embeddings())

    assert len(retriever.invoke("anything")) == RESULT_LIMIT
