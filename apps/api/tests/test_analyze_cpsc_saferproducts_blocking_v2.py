from __future__ import annotations

from scripts.analyze_cpsc_saferproducts_blocking_v2 import (
    compact,
    cpsc_product_tokens,
    normalize_text,
)


def test_text_normalization() -> None:
    assert normalize_text("Harbor-Breeze 54") == "harbor breeze 54"


def test_compact_upc() -> None:
    assert compact("082392-599195") == "082392599195"


def test_product_tokens() -> None:
    recall = {
        "products": [
            {
                "name": "Harbor Breeze Santa Ana Ceiling Fan",
            }
        ]
    }

    assert cpsc_product_tokens(recall) == {
        "harbor", "breeze", "santa", "ana", "ceiling", "fan"
    }
