from __future__ import annotations

import json
from pathlib import Path

from scripts.build_amazon_cpsc_index import build_index
from scripts.build_cpsc_amazon_candidates import generate_candidates


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_bounded_index_keeps_only_rare_query_tokens(tmp_path):
    cpsc = tmp_path / "cpsc.jsonl"
    amazon = tmp_path / "amazon.jsonl"

    write_jsonl(
        cpsc,
        [{"recall_number": "R1", "products": [{"name": "Rare Gizmo"}]}],
    )

    rows = [{"parent_asin": f"A{i}", "title": "Common Product"} for i in range(300)]
    rows.append({"parent_asin": "R", "title": "Rare Gizmo"})
    write_jsonl(amazon, rows)

    index = build_index(cpsc, amazon)

    assert "rare" in index["rare_postings"]
    assert "gizmo" in index["rare_postings"]
    assert "common" not in index["rare_postings"]


def test_candidate_generation_requires_two_shared_rare_tokens():
    index = {
        "blocker": {
            "max_token_document_frequency": 250,
            "min_shared_tokens": 2,
        },
        "exact_upc_index": {},
        "rare_postings": {
            "example": ["A1"],
            "steamer": ["A1"],
            "coffee": ["A2"],
        },
        "amazon_products": {
            "A1": {"title": "Example Steamer"},
            "A2": {"title": "Example Coffee"},
        },
    }

    exact, lexical, tokens = generate_candidates(
        {"name": "Example Steamer"},
        {},
        index,
    )

    assert exact == set()
    assert lexical == {"A1"}
    assert tokens == {"example", "steamer"}
