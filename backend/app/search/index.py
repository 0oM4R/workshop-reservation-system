"""Rank workshops in memory by keyword, semantic or hybrid search."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import InMemoryVectorStore, VectorStoreRetriever
from py_rust_stemmers import SnowballStemmer

RESULT_LIMIT = 10
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
