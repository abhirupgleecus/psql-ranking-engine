"""Unit tests for the RRF (Reciprocal Rank Fusion) merge algorithm.

Tests cover: fully disjoint lists, fully overlapping lists, partial overlap,
empty lists, and custom k values. All tests are pure (no DB, no I/O).
"""

from uuid import UUID

import pytest

from app.rrf import merge_rrf


# Deterministic UUIDs for test clarity
UUID_A = UUID("00000000-0000-0000-0000-000000000001")
UUID_B = UUID("00000000-0000-0000-0000-000000000002")
UUID_C = UUID("00000000-0000-0000-0000-000000000003")
UUID_D = UUID("00000000-0000-0000-0000-000000000004")
UUID_E = UUID("00000000-0000-0000-0000-000000000005")
UUID_F = UUID("00000000-0000-0000-0000-000000000006")


class TestFullyDisjoint:
    """Two lists with no common UUIDs."""

    def test_all_items_present(self):
        lexical = [(UUID_A, 0.8), (UUID_B, 0.5)]
        semantic = [(UUID_C, 0.1), (UUID_D, 0.3)]

        results = merge_rrf(lexical, semantic, k=60)

        result_uuids = {r["uuid"] for r in results}
        assert result_uuids == {UUID_A, UUID_B, UUID_C, UUID_D}

    def test_single_source_matched_in(self):
        lexical = [(UUID_A, 0.8)]
        semantic = [(UUID_C, 0.1)]

        results = merge_rrf(lexical, semantic, k=60)

        lex_result = next(r for r in results if r["uuid"] == UUID_A)
        sem_result = next(r for r in results if r["uuid"] == UUID_C)

        assert lex_result["matched_in"] == ["lexical"]
        assert lex_result["semantic_rank"] is None
        assert lex_result["semantic_distance"] is None

        assert sem_result["matched_in"] == ["semantic"]
        assert sem_result["lexical_rank"] is None
        assert sem_result["lexical_score"] is None

    def test_same_rank_equal_scores(self):
        """Items at the same rank in different lists get equal RRF scores."""
        lexical = [(UUID_A, 0.9)]
        semantic = [(UUID_B, 0.1)]

        results = merge_rrf(lexical, semantic, k=60)

        score_a = next(r for r in results if r["uuid"] == UUID_A)["rrf_score"]
        score_b = next(r for r in results if r["uuid"] == UUID_B)["rrf_score"]

        # Both at rank 1 → 1/(60+1) = same RRF score
        assert abs(score_a - score_b) < 1e-10


class TestFullyOverlapping:
    """Identical UUIDs in both lists."""

    def test_all_matched_in_both(self):
        lexical = [(UUID_A, 0.8), (UUID_B, 0.5)]
        semantic = [(UUID_A, 0.1), (UUID_B, 0.3)]

        results = merge_rrf(lexical, semantic, k=60)

        for r in results:
            assert "lexical" in r["matched_in"]
            assert "semantic" in r["matched_in"]
            assert r["lexical_rank"] is not None
            assert r["semantic_rank"] is not None

    def test_scores_are_sum_of_contributions(self):
        lexical = [(UUID_A, 0.8)]
        semantic = [(UUID_A, 0.1)]

        results = merge_rrf(lexical, semantic, k=60)
        result = results[0]

        expected_score = 1.0 / (60 + 1) + 1.0 / (60 + 1)  # rank 1 in both
        assert abs(result["rrf_score"] - expected_score) < 1e-10

    def test_preserves_original_scores(self):
        lexical = [(UUID_A, 0.85)]
        semantic = [(UUID_A, 0.12)]

        results = merge_rrf(lexical, semantic, k=60)
        result = results[0]

        assert result["lexical_score"] == 0.85
        assert result["semantic_distance"] == 0.12


class TestPartialOverlap:
    """Some shared UUIDs, some unique to each list."""

    def test_overlap_boost(self):
        """Item appearing in both lists scores higher than any single-list item."""
        # UUID_B appears in both lists (rank 2 in each)
        # UUID_A appears only in lexical (rank 1)
        # UUID_C appears only in semantic (rank 1)
        lexical = [(UUID_A, 0.9), (UUID_B, 0.7)]
        semantic = [(UUID_C, 0.05), (UUID_B, 0.15)]

        results = merge_rrf(lexical, semantic, k=60)

        score_a = next(r for r in results if r["uuid"] == UUID_A)["rrf_score"]
        score_b = next(r for r in results if r["uuid"] == UUID_B)["rrf_score"]
        score_c = next(r for r in results if r["uuid"] == UUID_C)["rrf_score"]

        # B (in both at rank 2): 1/(60+2) + 1/(60+2) = 2/(62) ≈ 0.0323
        # A (lexical rank 1 only): 1/(60+1) ≈ 0.0164
        # C (semantic rank 1 only): 1/(60+1) ≈ 0.0164
        assert score_b > score_a, "Overlapping item should beat single-list rank-1 item"
        assert score_b > score_c, "Overlapping item should beat single-list rank-1 item"

    def test_correct_matched_in(self):
        lexical = [(UUID_A, 0.9), (UUID_B, 0.7)]
        semantic = [(UUID_C, 0.05), (UUID_B, 0.15)]

        results = merge_rrf(lexical, semantic, k=60)

        result_a = next(r for r in results if r["uuid"] == UUID_A)
        result_b = next(r for r in results if r["uuid"] == UUID_B)
        result_c = next(r for r in results if r["uuid"] == UUID_C)

        assert result_a["matched_in"] == ["lexical"]
        assert sorted(result_b["matched_in"]) == ["lexical", "semantic"]
        assert result_c["matched_in"] == ["semantic"]

    def test_ranks_preserved(self):
        lexical = [(UUID_A, 0.9), (UUID_B, 0.7), (UUID_D, 0.3)]
        semantic = [(UUID_C, 0.05), (UUID_B, 0.15), (UUID_E, 0.4)]

        results = merge_rrf(lexical, semantic, k=60)

        result_b = next(r for r in results if r["uuid"] == UUID_B)
        assert result_b["lexical_rank"] == 2
        assert result_b["semantic_rank"] == 2
        assert result_b["lexical_score"] == 0.7
        assert result_b["semantic_distance"] == 0.15


class TestEmptyLists:
    """Edge cases with empty input lists."""

    def test_empty_lexical(self):
        semantic = [(UUID_A, 0.1), (UUID_B, 0.3)]

        results = merge_rrf([], semantic, k=60)

        assert len(results) == 2
        for r in results:
            assert r["matched_in"] == ["semantic"]
            assert r["lexical_rank"] is None
            assert r["lexical_score"] is None

    def test_empty_semantic(self):
        lexical = [(UUID_A, 0.8), (UUID_B, 0.5)]

        results = merge_rrf(lexical, [], k=60)

        assert len(results) == 2
        for r in results:
            assert r["matched_in"] == ["lexical"]
            assert r["semantic_rank"] is None
            assert r["semantic_distance"] is None

    def test_both_empty(self):
        results = merge_rrf([], [], k=60)
        assert results == []


class TestCustomK:
    """Non-default k value produces correct scores."""

    def test_k_10(self):
        lexical = [(UUID_A, 0.8)]
        semantic = [(UUID_A, 0.1)]

        results = merge_rrf(lexical, semantic, k=10)
        result = results[0]

        # rank 1 in both, k=10: 1/(10+1) + 1/(10+1) = 2/11
        expected = 2.0 / 11.0
        assert abs(result["rrf_score"] - expected) < 1e-10

    def test_k_1(self):
        lexical = [(UUID_A, 0.8), (UUID_B, 0.5)]

        results = merge_rrf(lexical, [], k=1)

        score_a = next(r for r in results if r["uuid"] == UUID_A)["rrf_score"]
        score_b = next(r for r in results if r["uuid"] == UUID_B)["rrf_score"]

        # k=1: rank 1 → 1/(1+1) = 0.5, rank 2 → 1/(1+2) ≈ 0.333
        assert abs(score_a - 0.5) < 1e-10
        assert abs(score_b - 1.0 / 3.0) < 1e-10

    def test_higher_k_reduces_score_spread(self):
        """Higher k values compress the score range between ranks."""
        lexical = [(UUID_A, 0.9), (UUID_B, 0.1)]

        results_k10 = merge_rrf(lexical, [], k=10)
        results_k1000 = merge_rrf(lexical, [], k=1000)

        spread_k10 = abs(
            next(r for r in results_k10 if r["uuid"] == UUID_A)["rrf_score"]
            - next(r for r in results_k10 if r["uuid"] == UUID_B)["rrf_score"]
        )
        spread_k1000 = abs(
            next(r for r in results_k1000 if r["uuid"] == UUID_A)["rrf_score"]
            - next(r for r in results_k1000 if r["uuid"] == UUID_B)["rrf_score"]
        )

        assert spread_k1000 < spread_k10, "Higher k should compress score spread"


class TestSortOrder:
    """Verify result ordering."""

    def test_descending_rrf_score(self):
        lexical = [(UUID_A, 0.9), (UUID_B, 0.7), (UUID_C, 0.3)]
        semantic = [(UUID_D, 0.1), (UUID_E, 0.2), (UUID_F, 0.4)]

        results = merge_rrf(lexical, semantic, k=60)
        scores = [r["rrf_score"] for r in results]

        assert scores == sorted(scores, reverse=True)

    def test_tiebreaker_lexical_preferred(self):
        """At equal RRF scores, item with lexical match (lower lexical_rank) wins."""
        # Both at rank 1 in their respective lists → same RRF score
        lexical = [(UUID_A, 0.9)]
        semantic = [(UUID_B, 0.1)]

        results = merge_rrf(lexical, semantic, k=60)

        # UUID_A has lexical_rank=1, UUID_B has lexical_rank=None (→ inf)
        # So UUID_A should come first
        assert results[0]["uuid"] == UUID_A
        assert results[1]["uuid"] == UUID_B
