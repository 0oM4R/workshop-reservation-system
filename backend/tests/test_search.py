"""Tests for workshop search: its building blocks, then GET /api/workshops/search."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding, Embeddings

from app.main import app
from app.search import index as search_index_module
from app.search.index import (
    RESULT_LIMIT,
    SearchDocument,
    SearchIndex,
    SearchMode,
    build_keyword_retriever,
    build_semantic_retriever,
    fuse_by_reciprocal_rank,
    get_search_index,
    load_search_index,
    tokenize,
    workshop_ids_of,
)
from tests.helpers import CreateWorkshop

SOURDOUGH = SearchDocument(
    1, "Sourdough Baking", "Bake a loaf of sourdough bread from your own starter."
)
PASTRY = SearchDocument(2, "Pastry Basics", "Bake bread rolls and croissants.")
BIKES = SearchDocument(3, "Bike Repair", "Fix a flat tire and adjust the brakes.")
QUERY = "sourdough bread"
MODES = [SearchMode.KEYWORD, SearchMode.SEMANTIC, SearchMode.HYBRID]
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


def build_index() -> SearchIndex:
    """Index the three sample workshops with the lookup embeddings."""
    return SearchIndex([SOURDOUGH, PASTRY, BIKES], LookupEmbeddings(VECTORS))


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


def test_fusion_puts_workshops_both_lists_rank_well_first() -> None:
    """Second and first (1/62 + 1/61) beats first and third (1/61 + 1/63)."""
    keyword_ids = [1, 2]
    semantic_ids = [2, 3, 1]

    assert fuse_by_reciprocal_rank(
        keyword_ids=keyword_ids, semantic_ids=semantic_ids
    ) == [2, 1, 3]


def test_fusion_breaks_ties_in_favor_of_keyword() -> None:
    """Equal scores: the keyword match comes first."""
    assert fuse_by_reciprocal_rank(semantic_ids=[7], keyword_ids=[5]) == [5, 7]


# The wired-up index and GET /api/workshops/search.


async def test_keyword_ranks_by_shared_terms_and_leaves_out_the_rest() -> None:
    """Two shared terms beat one; no shared term, no match."""
    assert await build_index().search(QUERY, SearchMode.KEYWORD) == [1, 2]


async def test_keyword_finds_nothing_without_a_shared_term() -> None:
    """No zero-score padding: an unknown word matches no workshop."""
    assert await build_index().search("kubernetes", SearchMode.KEYWORD) == []


@pytest.mark.parametrize(
    ("titles", "expected"),
    [
        (["Pottery"], [1]),
        (["Pottery", "Baking"], [1]),
        (["Pottery", "Pottery Wheel", "Baking", "Bike Repair"], [1, 2]),
    ],
    ids=["one workshop", "two workshops", "term in half the workshops"],
)
async def test_keyword_keeps_matches_that_bm25_scores_zero_or_below(
    titles: list[str], expected: list[int]
) -> None:
    """A shared term matches even when BM25 scores it 0 or less."""
    documents: list[SearchDocument] = []
    for number, title in enumerate(titles, start=1):
        documents.append(SearchDocument(number, title, ""))
    index = SearchIndex(documents, fake_embeddings())

    assert await index.search("pottery", SearchMode.KEYWORD) == expected


async def test_semantic_ranks_every_workshop_by_similarity() -> None:
    """Closest vectors first, even Bikes, which shares no word with the query."""
    assert await build_index().search(QUERY, SearchMode.SEMANTIC) == [2, 3, 1]


async def test_hybrid_fuses_keyword_and_semantic_ranks() -> None:
    """Keyword [1, 2] and semantic [2, 3, 1] fuse to Pastry, Sourdough, Bikes."""
    assert await build_index().search(QUERY, SearchMode.HYBRID) == [2, 1, 3]


@pytest.mark.parametrize("mode", MODES)
async def test_search_returns_at_most_the_result_limit(mode: SearchMode) -> None:
    """Even when every workshop matches, return only the top results."""
    documents: list[SearchDocument] = []
    for number in range(1, RESULT_LIMIT + 5):
        documents.append(
            SearchDocument(number, f"Workshop {number}", "Learn something new.")
        )
    index = SearchIndex(documents, fake_embeddings())

    assert len(await index.search("learn", mode)) == RESULT_LIMIT


@pytest.mark.parametrize("mode", MODES)
async def test_an_empty_index_finds_nothing(mode: SearchMode) -> None:
    """No workshops, no results."""
    index = SearchIndex([], fake_embeddings())

    assert await index.search(QUERY, mode) == []


async def test_workshops_made_only_of_stop_words_are_found_only_by_meaning() -> None:
    """BM25 can't index them, so keyword finds nothing; semantic and hybrid do."""
    index = SearchIndex([SearchDocument(1, "The", "and")], fake_embeddings())

    assert await index.search("the", SearchMode.KEYWORD) == []
    assert await index.search("the", SearchMode.SEMANTIC) == [1]
    assert await index.search("the", SearchMode.HYBRID) == [1]


def fake_model(model_name: str) -> Embeddings:
    """Stand in for the local model, which tests never download."""
    return fake_embeddings()


async def test_startup_indexes_every_workshop_in_the_database(
    create_workshop: CreateWorkshop, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The startup index reads every workshop from Postgres, for both modes."""
    monkeypatch.setattr(search_index_module, "FastEmbedEmbeddings", fake_model)
    pottery = await create_workshop("pottery")
    baking = await create_workshop("baking")
    bikes = await create_workshop("bikes")

    index = await load_search_index()

    assert await index.search("pottery", SearchMode.KEYWORD) == [pottery]
    semantic_ids = await index.search("pottery", SearchMode.SEMANTIC)
    assert sorted(semantic_ids) == sorted([pottery, baking, bikes])


@pytest.fixture
async def search_client() -> AsyncIterator[AsyncClient]:
    """HTTP client searching the three sample workshops."""
    index = build_index()
    app.dependency_overrides[get_search_index] = lambda: index
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    del app.dependency_overrides[get_search_index]


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("keyword", [1, 2]), ("semantic", [2, 3, 1]), ("hybrid", [2, 1, 3])],
)
async def test_search_endpoint_ranks_by_the_chosen_mode(
    search_client: AsyncClient, mode: str, expected: list[int]
) -> None:
    """The query is trimmed, and `mode` picks the ranking."""
    response = await search_client.get(
        "/api/workshops/search", params={"q": f"  {QUERY} ", "mode": mode}
    )

    assert response.status_code == 200
    assert response.json() == expected


async def test_search_endpoint_defaults_to_hybrid(search_client: AsyncClient) -> None:
    """Without a mode, results are the fused ranking."""
    response = await search_client.get("/api/workshops/search", params={"q": QUERY})

    assert response.status_code == 200
    assert response.json() == [2, 1, 3]


@pytest.mark.parametrize(
    "params",
    [{}, {"q": ""}, {"q": "   "}, {"q": "x" * 201}, {"q": QUERY, "mode": "fuzzy"}],
    ids=["missing", "empty", "blank", "too long", "unknown mode"],
)
async def test_search_endpoint_rejects_invalid_input(
    search_client: AsyncClient, params: dict[str, str]
) -> None:
    """A missing, blank or overlong query, or an unknown mode, returns 422."""
    response = await search_client.get("/api/workshops/search", params=params)

    assert response.status_code == 422
