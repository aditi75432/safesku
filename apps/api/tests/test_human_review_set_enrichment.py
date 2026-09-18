from __future__ import annotations

from scripts.build_linkage_review_set import join_source_evidence, prepare_output_rows


def test_join_source_evidence_populates_identity_evidence() -> None:
    selected = [
        {
            "cpsc_source_record_id": "R1",
            "saferproducts_source_record_id": "I1",
            "cpsc_recall_number": "12345",
            "cpsc_recall_date": "2022-01-01",
            "cpsc_product_name": "Example Widget",
            "incident_date": "2021-01-01",
            "publication_date": "2021-01-15",
            "initial_label": "positive_seed",
            "exact_upc": 1,
        }
    ]
    candidates = [
        {
            "cpsc_source_record_id": "R1",
            "saferproducts_source_record_id": "I1",
            "incident_brand": "Example",
            "incident_model": "X1",
            "incident_upc": "012345678901",
            "incident_product_description": "Example Widget X1",
        }
    ]
    recalls = [
        {
            "source_record_id": "R1",
            "title": "Example Widget Recall",
            "description": "A product description",
            "hazards": ["fire"],
            "manufacturers": ["Example Corp"],
            "retailers": ["Retailer"],
            "url": "https://example.com/recall",
        }
    ]
    incidents = [
        {
            "source_record_id": "I1",
            "incident_description": "The widget overheated.",
            "product_category": "Widgets",
            "manufacturer_name": "Example Corp",
            "retailer_name": "Retailer",
            "locale": "US",
            "product_purchased_date": "2020-12-01",
            "product_manufactured_date": "2020-11-01",
            "manufacturer_comments": "Example comment",
            "user_still_has_product": True,
            "severity_type_id": "1",
        }
    ]

    enriched = join_source_evidence(selected, candidates, recalls, incidents)
    output = prepare_output_rows(enriched)

    assert output[0]["incident_brand"] == "Example"
    assert output[0]["incident_model"] == "X1"
    assert output[0]["incident_product_description"] == "Example Widget X1"
    assert output[0]["incident_description"] == "The widget overheated."
    assert output[0]["cpsc_hazards"] == ["fire"]
    assert output[0]["cpsc_url"] == "https://example.com/recall"
    assert output[0]["temporal_status"] == "pre_recall_public"


def test_join_source_evidence_fails_loudly_on_missing_source() -> None:
    selected = [{"cpsc_source_record_id": "R1", "saferproducts_source_record_id": "I1"}]
    try:
        join_source_evidence(selected, [], [], [])
    except ValueError as exc:
        assert "Source join incomplete" in str(exc)
    else:
        raise AssertionError("Expected ValueError for an incomplete source join")
