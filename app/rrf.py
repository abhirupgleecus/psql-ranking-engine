"""Reciprocal Rank Fusion (RRF) merge algorithm.

Combines ranked lists from multiple retrieval passes into a single
fused ranking. Based on the original RRF paper by Cormack, Clarke, and Büttcher.

RRF_score(doc) = Σ over lists containing doc of [ 1 / (k + rank_in_that_list) ]

The default k=60 is the industry-standard value from the original paper,
also used by Elasticsearch and OpenSearch.
"""

from uuid import UUID


def merge_rrf(
    lexical_results: list[tuple[UUID, float]],
    semantic_results: list[tuple[UUID, float]],
    k: int = 60,
) -> list[dict]:
    """Merge two ranked lists using Reciprocal Rank Fusion.

    Args:
        lexical_results: List of (uuid, score) tuples from lexical retrieval,
            ordered by rank (best first). Score is the ts_rank_cd value
            (or 1.0 + boost for wildcard fallback).
        semantic_results: List of (uuid, distance) tuples from semantic retrieval,
            ordered by rank (best/closest first). Distance is the pgvector
            cosine distance (lower = more similar).
        k: RRF constant (default 60). Higher values reduce the influence
            of high-ranked items.

    Returns:
        List of dicts sorted by rrf_score descending. Each dict contains:
        - uuid: The product UUID
        - rrf_score: The fused RRF score
        - matched_in: List of sources (["lexical"], ["semantic"], or both)
        - lexical_rank: 1-indexed position in lexical list, or None
        - lexical_score: The ts_rank_cd score, or None
        - semantic_rank: 1-indexed position in semantic list, or None
        - semantic_distance: The cosine distance, or None
    """
    fused: dict[UUID, dict] = {}

    # Process lexical results
    for i, (uuid, score) in enumerate(lexical_results):
        rank = i + 1  # 1-indexed
        rrf_contribution = 1.0 / (k + rank)

        if uuid not in fused:
            fused[uuid] = {
                "uuid": uuid,
                "rrf_score": 0.0,
                "matched_in": [],
                "lexical_rank": None,
                "lexical_score": None,
                "semantic_rank": None,
                "semantic_distance": None,
            }

        fused[uuid]["rrf_score"] += rrf_contribution
        fused[uuid]["matched_in"].append("lexical")
        fused[uuid]["lexical_rank"] = rank
        fused[uuid]["lexical_score"] = score

    # Process semantic results
    for i, (uuid, distance) in enumerate(semantic_results):
        rank = i + 1  # 1-indexed
        rrf_contribution = 1.0 / (k + rank)

        if uuid not in fused:
            fused[uuid] = {
                "uuid": uuid,
                "rrf_score": 0.0,
                "matched_in": [],
                "lexical_rank": None,
                "lexical_score": None,
                "semantic_rank": None,
                "semantic_distance": None,
            }

        fused[uuid]["rrf_score"] += rrf_contribution
        fused[uuid]["matched_in"].append("semantic")
        fused[uuid]["semantic_rank"] = rank
        fused[uuid]["semantic_distance"] = distance

    # Sort by rrf_score descending, then by lexical_rank ascending as tiebreaker
    # (lexical match preferred at tie; items without lexical_rank sort last)
    results = sorted(
        fused.values(),
        key=lambda x: (
            -x["rrf_score"],
            x["lexical_rank"] if x["lexical_rank"] is not None else float("inf"),
        ),
    )

    return results
