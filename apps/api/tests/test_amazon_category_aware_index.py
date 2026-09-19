from __future__ import annotations

import json
from pathlib import Path

from scripts.build_amazon_cpsc_index import build_index
from scripts.build_cpsc_amazon_candidates import generate_candidates


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_token_can_be_common_globally_but_rare_in_category(tmp_path):
    cpsc = tmp_path / "cpsc.jsonl"
    amazon = tmp_path / "amazon.jsonl"
    write_jsonl(cpsc, [{"recall_number": "R1", "products": [{"name": "Rare Gizmo"}]}])
    rows = [
        {"parent_asin": f"E{i}", "title": "Common Gizmo", "source_category": "Electronics"}
        for i in range(300)
    ]
    rows.append({"parent_asin": "B1", "title": "Rare Gizmo", "source_category": "Baby_Products"})
    write_jsonl(amazon, rows)

    index = build_index(cpsc, amazon)

    assert "gizmo" in index["rare_postings"]
    assert "B1" in index["rare_postings"]["gizmo"]
    assert "E0" not in index["rare_postings"]["gizmo"]


def test_token_common_within_category_is_removed(tmp_path):
    cpsc = tmp_path / "cpsc.jsonl"
    amazon = tmp_path / "amazon.jsonl"
    write_jsonl(cpsc, [{"recall_number": "R1", "products": [{"name": "Common Gizmo"}]}])
    rows = [
        {"parent_asin": f"A{i}", "title": "Common Gizmo", "source_category": "Electronics"}
        for i in range(300)
    ]
    write_jsonl(amazon, rows)

    index = build_index(cpsc, amazon)
    assert "common" not in index["rare_postings"]
    assert "gizmo" not in index["rare_postings"]


def test_candidate_uses_full_title_after_rare_seed():
    index = {
        "version": 2,
        "blocker": {"max_token_document_frequency": 250, "min_shared_tokens": 2},
        "exact_upc_index": {},
        "rare_postings": {"hgs011": ["A1"]},
        "amazon_products": {"A1": {"title": "Black Decker HGS011 Steamer"}},
    }
    exact, lexical, _ = generate_candidates({"name": "BLACK DECKER HGS011"}, {}, index)
    assert exact == set()
    assert lexical == {"A1"}
