from __future__ import annotations

from scripts.profile_cpsc_benchmark import build_profile


def test_profile_counts_populated_product_fields() -> None:
    rows = [
        {
            "description": "Recall description",
            "hazards": [{"name": "Hazard"}],
            "product_upcs": ["123"],
            "products": [
                {
                    "name": "Example Product",
                    "type": None,
                    "category_id": None,
                    "model": "M-1",
                    "number_of_units": "About 10",
                }
            ],
        }
    ]

    profile = build_profile(rows)

    assert profile["recall_count"] == 1
    assert profile["product_record_count"] == 1
    assert profile["product_fields"]["name"] == 1
    assert profile["product_fields"]["type"] == 0
    assert profile["product_fields"]["category_id"] == 0
    assert profile["product_fields"]["model"] == 1
    assert profile["recall_fields"]["product_upcs"] == 1
