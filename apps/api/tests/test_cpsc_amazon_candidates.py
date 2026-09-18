from __future__ import annotations

import json
from pathlib import Path

from scripts.build_cpsc_amazon_candidates import build_indices, generate_candidates


def write_jsonl(path: Path, rows):
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_generic_brand_like_tokens_do_not_block_without_two_shared_tokens(tmp_path):
    amazon = tmp_path / "amazon.jsonl"
    write_jsonl(
        amazon,
        [
            {"parent_asin": "A1", "title": "Baby Product"},
            {"parent_asin": "A2", "title": "Baby Toy"},
        ],
    )
    _, upc_index, token_index = build_indices(amazon)
    exact, lexical, _, _ = generate_candidates(
        {"name": "Baby Blanket"},
        {},
        upc_index,
        token_index,
        max_token_document_frequency=250,
        min_shared_tokens=2,
    )
    assert exact == set()
    assert lexical == set()


def test_two_shared_tokens_plus_rare_term_create_candidate(tmp_path):
    amazon = tmp_path / "amazon.jsonl"
    write_jsonl(
        amazon,
        [
            {"parent_asin": "A1", "title": "Example HGS011 Steamer"},
            {"parent_asin": "A2", "title": "Example Coffee Maker"},
            {"parent_asin": "A3", "title": "Example Blender"},
        ],
    )
    _, upc_index, token_index = build_indices(amazon)
    exact, lexical, _, _ = generate_candidates(
        {"name": "Example HGS011 Steamer"},
        {},
        upc_index,
        token_index,
        max_token_document_frequency=2,
        min_shared_tokens=2,
    )
    assert exact == set()
    assert lexical == {"A1"}
