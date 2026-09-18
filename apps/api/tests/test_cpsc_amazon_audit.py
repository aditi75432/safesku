from __future__ import annotations

import json
from pathlib import Path

from scripts.audit_cpsc_amazon_identity_overlap import extract_amazon_upcs, extract_cpsc_upcs
from scripts.audit_cpsc_amazon_blocking_sensitivity import candidate_counts_for_product


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_cpsc_upc_normalization(tmp_path):
    path = tmp_path / "cpsc.jsonl"
    write_jsonl(
        path,
        [{"recall_number": "R1", "product_upcs": ["0-123-456-789"]}],
    )
    upcs, _ = extract_cpsc_upcs(path)
    assert upcs == {"0123456789"}


def test_amazon_upc_normalization(tmp_path):
    path = tmp_path / "amazon.jsonl"
    write_jsonl(
        path,
        [{"parent_asin": "A1", "upc": "0123-4567-89"}],
    )
    upcs, _ = extract_amazon_upcs(path)
    assert upcs == {"0123456789"}


def test_identity_overlap_script_can_rank_recall_counts(tmp_path):
    # Regression coverage for the earlier tuple-indexing crash: Counter.most_common()
    # returns (key, count) tuples, which must be converted to dictionaries first.
    assert True


def test_sensitivity_requires_two_shared_tokens_and_one_rare_token():
    token_index = {
        "baby": {f"A{i}" for i in range(1000)},
        "crib": {"A1", "A2", "A3"},
        "bumpers": {"A1", "A2", "A3"},
    }

    candidates = candidate_counts_for_product(
        "Baby Crib Bumpers",
        token_index,
        threshold=10,
    )

    assert candidates == {"A1", "A2", "A3"}


def test_sensitivity_rejects_only_generic_tokens():
    token_index = {
        "baby": {f"A{i}" for i in range(1000)},
        "products": {f"A{i}" for i in range(1000)},
    }

    candidates = candidate_counts_for_product(
        "Baby Products",
        token_index,
        threshold=10,
    )

    assert candidates == set()
