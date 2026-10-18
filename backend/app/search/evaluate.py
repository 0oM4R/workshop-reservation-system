"""Evaluate search relevance on the demo catalog with the bundled model.

Run with `python -m app.search.evaluate` inside the API image.
"""

import asyncio

from app.search.index import (
    EMBEDDING_MODEL,
    SearchDocument,
    SearchIndex,
    SearchMode,
    load_embeddings,
)
from app.seed import DEMO_WORKSHOPS

# One intended destination per query; labels are independent of search results.
QUERIES = [
    ("sourdough baking", "sourdough-baking"),
    ("SQL from scratch", "sql-from-scratch"),
    ("fix a puncture on my bicycle", "bike-repair-101"),
    ("make a bowl out of clay", "intro-to-pottery"),
    ("tidy up an Excel sheet full of errors", "spreadsheet-data-cleaning"),
    ("analyze datasets using pandas", "python-data-analysis"),
    ("protect a website against injection attacks", "secure-coding"),
    ("automate testing and deploying each commit", "continuous-delivery"),
    ("resolve merge conflicts with colleagues", "git-for-teams"),
    ("feel less nervous presenting to an audience", "public-speaking"),
    ("I just became a manager and need to delegate", "first-time-managers"),
    ("ease my stiff neck after sitting at a computer", "desk-yoga"),
    ("grow herbs on my apartment windowsill", "balcony-gardening"),
    ("make ravioli by hand", "fresh-pasta"),
    ("practice ordering dinner in Spanish", "spanish-for-travelers"),
    ("handle an outage while on call", "incident-response"),
    # Other workshops share words with these, so matching words alone misleads.
    ("pick the right graph for my slides", "data-storytelling"),
    ("stop feeling burned out at work", "mindfulness-stress"),
    ("make my website usable for blind visitors", "web-accessibility"),
    ("spot risks in our system design before writing code", "threat-modeling"),
]
HIT_CUTOFF = 3
RANK_CUTOFF = 10


def score(ranked_ids: list[int], expected_id: int) -> tuple[float, float]:
    """Return Hit@3 and reciprocal rank at 10 for one intended workshop.

    A hit is 1 when the target is in the first three results, otherwise 0.
    Reciprocal rank is 1 divided by the target's position: 1, 0.5, 0.333, etc.
    Both scores are 0 when the target is absent from the first ten results.
    """
    for rank, workshop_id in enumerate(ranked_ids[:RANK_CUTOFF], start=1):
        if workshop_id == expected_id:
            hit = 0.0
            if rank <= HIT_CUTOFF:
                hit = 1.0
            reciprocal_rank = 1 / rank
            return hit, reciprocal_rank
    return 0.0, 0.0


async def evaluate_mode(
    search_index: SearchIndex, ids_by_slug: dict[str, int], mode: SearchMode
) -> tuple[float, float]:
    """Print each query's top results in one mode; return Hit@3 and MRR@10."""
    total_hits = 0.0
    total_reciprocal_rank = 0.0
    print(f"\n{'=' * 64}\n{mode.upper()}\n{'=' * 64}")
    for query_number, (query, expected_slug) in enumerate(QUERIES, start=1):
        ranked_ids = await search_index.search(query, mode)
        expected_id = ids_by_slug[expected_slug]
        hit, reciprocal_rank = score(ranked_ids, expected_id)
        total_hits += hit
        total_reciprocal_rank += reciprocal_rank

        print(f"\n{query_number:02d}. {query}")
        print(f"    Expected: {DEMO_WORKSHOPS[expected_id].title}")
        print("    Top results:")
        for rank, workshop_id in enumerate(ranked_ids[:HIT_CUTOFF], start=1):
            print(f"      {rank}. {DEMO_WORKSHOPS[workshop_id].title}")
        if not ranked_ids:
            print("      No results")
        hit_label = "No"
        if hit:
            hit_label = "Yes"
        print(f"    Hit@3: {hit_label} | RR@10: {reciprocal_rank:.3f}")
    hit_rate = total_hits / len(QUERIES)
    mean_reciprocal_rank = total_reciprocal_rank / len(QUERIES)
    return hit_rate, mean_reciprocal_rank


def print_summary(summaries: list[tuple[str, float, float]]) -> None:
    """Print Hit@3 and MRR@10 for each mode as a table."""
    print(f"\n{'=' * 64}\nSUMMARY\n{'=' * 64}")
    print(f"{'Mode':<12} {'Hit@3':>10} {'MRR@10':>10}")
    print("-" * 34)
    for mode_name, hit_rate, mean_reciprocal_rank in summaries:
        print(f"{mode_name:<12} {hit_rate:>10.1%} {mean_reciprocal_rank:>10.3f}")
    print("\nHit@3 = share of queries with the expected workshop in the top three.")
    print("MRR@10 = average RR@10 across all queries. Higher is better (up to 1).")
    print("Small demo evaluation; scores are descriptive, not a pass/fail gate.")


async def main() -> None:
    """Print per-query results and mean relevance scores for each search mode."""
    documents: list[SearchDocument] = []
    ids_by_slug: dict[str, int] = {}
    # Use list positions as local IDs so evaluation needs no database.
    for workshop_id, workshop in enumerate(DEMO_WORKSHOPS):
        document = SearchDocument(workshop_id, workshop.title, workshop.description)
        documents.append(document)
        ids_by_slug[workshop.slug] = workshop_id

    print("\nSEARCH EVALUATION")
    print(f"Queries: {len(QUERIES)} | Workshops: {len(documents)}")
    print(f"Model: {EMBEDDING_MODEL}")
    print("Loading model and building index...", flush=True)
    search_index = SearchIndex(documents, load_embeddings())
    print("Hit@3: was the expected workshop in the first three results?")
    print("RR@10: 1 divided by its rank; 0 if absent from the first ten results.")
    summaries: list[tuple[str, float, float]] = []
    for mode in SearchMode:
        hit_rate, mean_reciprocal_rank = await evaluate_mode(
            search_index, ids_by_slug, mode
        )
        summaries.append((mode.value, hit_rate, mean_reciprocal_rank))
    print_summary(summaries)


if __name__ == "__main__":
    asyncio.run(main())
