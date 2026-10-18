"""Rank workshops in memory by keyword, semantic or hybrid search."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from fastapi import Request
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore, VectorStoreRetriever
from py_rust_stemmers import SnowballStemmer

from app.db import session_factory
from app.services import workshops

# Must match backend/Dockerfile, which downloads it at build time.
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RESULT_LIMIT = 10
# The usual reciprocal rank fusion offset: it keeps one list's first place
# from outweighing a workshop that ranks well in both lists.
RRF_RANK_OFFSET = 60
WORKSHOP_ID = "workshop_id"
# Common words would match unrelated workshops.
STOP_WORDS = frozenset(
    "a about an and are as at be by can do for from get how i in into is it me my "
    "of on or our so some something that the their them this to want we what "
    "with you your".split()
)
WORD = re.compile(r"[a-z0-9]+")
STEMMER = SnowballStemmer("english")


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


def tokenize(text: str) -> list[str]:
    """Lowercase, drop stop words and stem."""
    searchable_words: list[str] = []
    for word in WORD.findall(text.lower()):
        if word not in STOP_WORDS:
            searchable_words.append(STEMMER.stem_word(word))
    return searchable_words


class KeywordRetriever(BM25Retriever):
    """Return workshops sharing a query word, best BM25 score first."""

    def _score_matches(self, query: str) -> list[tuple[float, Document]]:
        """Return (score, document) for each document sharing a query word."""
        query_words = self.preprocess_func(query)
        scores = self.vectorizer.get_scores(query_words)
        word_counts_per_document = self.vectorizer.doc_freqs

        matches: list[tuple[float, Document]] = []
        for score, document, document_word_counts in zip(
            scores, self.docs, word_counts_per_document, strict=True
        ):
            has_matching_word = False
            for query_word in query_words:
                if query_word in document_word_counts:
                    has_matching_word = True
                    break

            if has_matching_word:
                matches.append((score, document))
        return matches

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        matches = self._score_matches(query)
        matches.sort(key=lambda match: match[0], reverse=True)
        documents: list[Document] = []
        for _score, document in matches[: self.k]:
            documents.append(document)
        return documents


def build_keyword_retriever(documents: list[Document]) -> BM25Retriever | None:
    """Build BM25, or return None when no document has a searchable word."""
    # BM25 crashes on zero words (no workshops, or only stop words).
    has_searchable_words = False
    for document in documents:
        if tokenize(document.page_content):
            has_searchable_words = True
            break

    if not has_searchable_words:
        return None

    return KeywordRetriever.from_documents(
        documents,
        preprocess_func=tokenize,
        k=RESULT_LIMIT,
    )


def build_semantic_retriever(
    documents: list[Document], embeddings: Embeddings
) -> VectorStoreRetriever:
    """Embed the documents into an in-memory vector retriever."""
    vector_store = InMemoryVectorStore(embedding=embeddings)
    vector_store.add_documents(documents)

    return vector_store.as_retriever(search_kwargs={"k": RESULT_LIMIT})


def add_rank_scores(scores: dict[int, float], ranked_ids: list[int]) -> None:
    """Add one ranking's contributions to the shared scores."""
    for rank, workshop_id in enumerate(ranked_ids, start=1):
        contribution = 1 / (RRF_RANK_OFFSET + rank)
        scores[workshop_id] = scores.get(workshop_id, 0.0) + contribution


def fuse_by_reciprocal_rank(
    *, keyword_ids: list[int], semantic_ids: list[int]
) -> list[int]:
    """Merge ranked workshop IDs: each list adds 1 / (RRF_RANK_OFFSET + rank)."""
    # Ranks, not scores: BM25 and cosine scores use different scales.
    scores: dict[int, float] = {}
    add_rank_scores(scores, keyword_ids)
    add_rank_scores(scores, semantic_ids)

    fused_ids = list(scores.keys())
    # The sort is stable, so tied workshops keep first-seen order: keyword first.
    fused_ids.sort(key=lambda workshop_id: scores[workshop_id], reverse=True)
    return fused_ids


class SearchIndex:
    """Search workshops by keyword, by meaning, or both."""

    def __init__(
        self, documents: Sequence[SearchDocument], embeddings: Embeddings
    ) -> None:
        """Build both retrievers; blocks while embedding."""
        retriever_documents: list[Document] = []
        for workshop in documents:
            retriever_documents.append(workshop.as_document())

        self._keyword_retriever = build_keyword_retriever(retriever_documents)
        self._semantic_retriever = build_semantic_retriever(
            retriever_documents, embeddings
        )

    async def search(self, query: str, mode: SearchMode) -> list[int]:
        """Return matching workshop IDs, best first."""
        if mode == SearchMode.KEYWORD:
            return await self._search_keyword(query)

        if mode == SearchMode.SEMANTIC:
            return await self._search_semantic(query)

        # Hybrid: both rankings, fused.
        keyword_ids = await self._search_keyword(query)
        semantic_ids = await self._search_semantic(query)
        hybrid_ids = fuse_by_reciprocal_rank(
            keyword_ids=keyword_ids, semantic_ids=semantic_ids
        )
        return hybrid_ids[:RESULT_LIMIT]

    async def _search_keyword(self, query: str) -> list[int]:
        """Return IDs of workshops sharing a word with the query, best first."""
        if self._keyword_retriever is None:
            return []

        matching_documents = await self._keyword_retriever.ainvoke(query)
        return workshop_ids_of(matching_documents)

    async def _search_semantic(self, query: str) -> list[int]:
        """Return IDs of the workshops closest in meaning, best first."""
        matching_documents = await self._semantic_retriever.ainvoke(query)
        return workshop_ids_of(matching_documents)


def load_embeddings() -> Embeddings:
    """Load the embedding model bundled in the API image."""
    return FastEmbedEmbeddings(model_name=EMBEDDING_MODEL)


async def load_search_index() -> SearchIndex:
    """Load every workshop's text and index it."""
    async with session_factory() as session:
        rows = await workshops.list_workshops(session)

    search_documents: list[SearchDocument] = []
    for row in rows:
        search_documents.append(SearchDocument(row.id, row.title, row.description))

    return SearchIndex(search_documents, load_embeddings())


def get_search_index(request: Request) -> SearchIndex:
    """Return the index built at startup."""
    return request.state.search_index
