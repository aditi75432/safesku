from __future__ import annotations

from scripts.analyze_cpsc_saferproducts_blocking import (
    candidate_count_stats,
    normalize_compact,
    normalize_text,
)


def test_normalize_text() -> None:
    assert normalize_text("  Harbor-Breeze  ") == "harbor breeze"


def test_normalize_compact() -> None:
    assert normalize_compact("0823-9259-9186") == "082392599186"


def test_candidate_count_stats() -> None:
    stats = candidate_count_stats([0, 1, 2, 3, 4])

    assert stats["min"] == 0
    assert stats["median"] == 2
    assert stats["max"] == 4
    assert stats["recalls_with_candidates"] == 4
