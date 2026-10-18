"""Check evaluation labels, metric boundaries and reporting without a real model."""

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

from app.search import evaluate
from app.search import index as search_index_module
from app.seed import DEMO_WORKSHOPS


@pytest.mark.parametrize(
    ("ranked_ids", "expected_id", "expected_scores"),
    [
        ([], 1, (0.0, 0.0)),
        ([2, 3], 1, (0.0, 0.0)),
        ([1, 2, 3], 1, (1.0, 1.0)),
        ([1, 2, 3], 3, (1.0, 1 / 3)),
        ([1, 2, 3, 4], 4, (0.0, 1 / 4)),
        (list(range(1, 12)), 10, (0.0, 1 / 10)),
        (list(range(1, 12)), 11, (0.0, 0.0)),
    ],
)
def test_score(
    ranked_ids: list[int], expected_id: int, expected_scores: tuple[float, float]
) -> None:
    """Score missing targets and both cutoff boundaries correctly."""
    assert evaluate.score(ranked_ids, expected_id) == expected_scores


def test_query_labels() -> None:
    """Keep at least 15 distinct valid queries with labels in the demo catalog."""
    queries = [query for query, _ in evaluate.QUERIES]
    slugs = {workshop.slug for workshop in DEMO_WORKSHOPS}
    assert len(queries) >= 15
    assert len(set(queries)) == len(queries)
    for query, slug in evaluate.QUERIES:
        assert query.strip() == query
        assert 1 <= len(query) <= 200
        assert slug in slugs


async def test_evaluation_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Run all queries and report scores for every mode using fake embeddings."""

    def fake_embeddings(*, model_name: str) -> DeterministicFakeEmbedding:
        assert model_name == search_index_module.EMBEDDING_MODEL
        return DeterministicFakeEmbedding(size=8)

    monkeypatch.setattr(search_index_module, "FastEmbedEmbeddings", fake_embeddings)
    await evaluate.main()
    output = capsys.readouterr().out
    mode_count = len(evaluate.SearchMode)
    assert f"Queries: {len(evaluate.QUERIES)}" in output
    assert "SUMMARY" in output
    for mode in evaluate.SearchMode:
        assert f"\n{mode.upper()}\n" in output
        assert f"\n{mode.value:<12} " in output
    titles_by_slug: dict[str, str] = {}
    for workshop in DEMO_WORKSHOPS:
        titles_by_slug[workshop.slug] = workshop.title
    for query_number, (query, slug) in enumerate(evaluate.QUERIES, start=1):
        assert output.count(f"{query_number:02d}. {query}\n") == mode_count
        assert output.count(f"Expected: {titles_by_slug[slug]}\n") == mode_count
    # One score line per query in each mode.
    assert output.count(" | RR@10: ") == len(evaluate.QUERIES) * mode_count
