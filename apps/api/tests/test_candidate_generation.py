from __future__ import annotations

from app.services.linkage.candidates import (
    build_token_index,
    build_upc_index,
    generate_candidates,
)


def test_generate_candidates_uses_upc_or_two_tokens() -> None:
    recall = {
        "source_record_id": "R1",
        "recall_number": "10001",
        "recall_date": "2022-01-01",
        "products": [{"name": "Acme Electric Grill"}],
        "product_upcs": ["111111111111"],
    }

    incidents = [
        {
            "source_record_id": "I1",
            "product_brand": "Acme",
            "product_model": "G100",
            "product_description": "Electric grill",
            "product_upc": "111111111111",
        },
        {
            "source_record_id": "I2",
            "product_brand": "Other",
            "product_model": None,
            "product_description": "Acme electric tool",
            "product_upc": None,
        },
        {
            "source_record_id": "I3",
            "product_brand": "Other",
            "product_model": None,
            "product_description": "Kitchen appliance",
            "product_upc": None,
        },
    ]

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }

    candidates = generate_candidates(
        recall,
        incidents_by_id,
        build_upc_index(incidents),
        build_token_index(incidents),
    )

    ids = {
        candidate.saferproducts_source_record_id
        for candidate in candidates
    }

    assert ids == {"I1", "I2"}
    assert candidates[0].saferproducts_source_record_id == "I1"
    assert candidates[0].exact_upc is True
    assert "exact_upc" in candidates[0].blocking_sources


def test_two_token_blocker_rejects_single_generic_overlap() -> None:
    recall = {
        "source_record_id": "R2",
        "products": [{"name": "Acme Electric Grill"}],
        "product_upcs": [],
    }

    incidents = [
        {
            "source_record_id": "I1",
            "product_brand": "Other",
            "product_model": None,
            "product_description": "Electric toaster",
            "product_upc": None,
        }
    ]

    candidates = generate_candidates(
        recall,
        {"I1": incidents[0]},
        build_upc_index(incidents),
        build_token_index(incidents),
    )

    assert candidates == []
