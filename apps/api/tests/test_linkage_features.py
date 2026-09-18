
from __future__ import annotations

from math import isclose
from types import SimpleNamespace

from app.services.linkage.features import (
    build_pair_features,
    similarity,
    token_jaccard,
)


def test_similarity_identical_values() -> None:
    assert similarity("HGS011", "HGS011") == 1.0


def test_token_jaccard() -> None:
    value = token_jaccard(
        {"electric", "grill"},
        {"electric", "grill", "portable"},
    )

    assert isclose(value, 2 / 3, rel_tol=0.0, abs_tol=1e-6)


def test_build_pair_features_detects_exact_upc() -> None:
    candidate = SimpleNamespace(
        cpsc_source_record_id="R1",
        cpsc_recall_number="10001",
        cpsc_recall_date="2022-01-01",
        cpsc_product_name="Acme Electric Grill",
        saferproducts_source_record_id="I1",
        exact_upc=True,
        blocking_sources=("exact_upc",),
        shared_product_tokens=("electric", "grill"),
        shared_product_token_count=2,
        product_token_jaccard=0.5,
        incident_date="2021-01-01",
        publication_date="2021-02-01",
    )

    recall = {
        "source_record_id": "R1",
        "product_upcs": ["111111111111"],
    }

    incident = {
        "source_record_id": "I1",
        "product_upc": "111111111111",
        "product_brand": "Acme",
        "product_model": "G100",
        "product_description": "Acme Electric Grill",
        "manufacturer_name": "Acme",
        "retailer_name": "Example",
    }

    features = build_pair_features(
        candidate,
        recall,
        incident,
    )

    assert features.exact_upc == 1
    assert features.product_name_substring == 1
    assert features.shared_product_token_count >= 2
    assert features.incident_model_in_cpsc_name == 0
