from __future__ import annotations

from scripts.build_cpsc_amazon_candidates import generate_candidates


def test_common_second_token_is_allowed_after_rare_seed():
    index = {
        "blocker": {"max_token_document_frequency": 250, "min_shared_tokens": 2},
        "exact_upc_index": {},
        "rare_postings": {
            "hgs011": ["A1"],
        },
        "amazon_products": {
            "A1": {"title": "Black Decker HGS011 Steamer"},
        },
    }

    exact, lexical, tokens = generate_candidates(
        {"name": "BLACK DECKER HGS011"},
        {},
        index,
    )

    assert exact == set()
    assert lexical == {"A1"}
    assert "hgs011" in tokens


def test_single_shared_rare_token_does_not_pass():
    index = {
        "blocker": {"max_token_document_frequency": 250, "min_shared_tokens": 2},
        "exact_upc_index": {},
        "rare_postings": {
            "hgs011": ["A1"],
        },
        "amazon_products": {
            "A1": {"title": "HGS011"},
        },
    }

    exact, lexical, _ = generate_candidates(
        {"name": "HGS011 Steamer"},
        {},
        index,
    )

    assert exact == set()
    assert lexical == set()
