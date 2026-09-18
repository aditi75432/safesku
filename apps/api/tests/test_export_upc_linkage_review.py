from __future__ import annotations

from scripts.export_upc_linkage_review import first_product


def test_first_product_handles_missing_products() -> None:
    assert first_product({"products": []}) == {}


def test_first_product_returns_first_product() -> None:
    recall = {"products": [{"name": "Example"}]}
    assert first_product(recall) == {"name": "Example"}
