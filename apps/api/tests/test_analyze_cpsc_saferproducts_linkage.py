from __future__ import annotations

from scripts.analyze_cpsc_saferproducts_linkage import (
    build_inverted_index,
    exact_upc_links,
    normalize_text,
    tokens,
)


def test_normalize_text() -> None:
    assert normalize_text("  ACME™ Bistro-Pro  ") == "acme bistro pro"


def test_tokens_drop_common_words() -> None:
    assert tokens("The Char-Broil Electric Grill") == {
        "char", "broil", "electric", "grill"
    }


def test_exact_upc_links() -> None:
    recalls = [
        {
            "source_record_id": "R1",
            "product_upcs": ["012345678901"],
        }
    ]
    incidents = [
        {
            "source_record_id": "I1",
            "product_upc": "012345678901",
        },
        {
            "source_record_id": "I2",
            "product_upc": "999999999999",
        },
    ]

    links = exact_upc_links(recalls, incidents)

    assert links == {"R1": ["I1"]}


def test_inverted_index() -> None:
    incidents = [
        {
            "source_record_id": "I1",
            "product_brand": "Acme",
            "product_model": "X100",
            "product_description": "Electric grill",
        }
    ]

    index = build_inverted_index(incidents)

    assert "acme" in index
    assert "x100" in index
    assert "electric" in index
    assert index["x100"] == {"I1"}
