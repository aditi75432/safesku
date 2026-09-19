from app.investigation.agent import _extract_marketplace_references


def test_extract_amazon_asin_from_incident():
    incidents = [{
        "source_record_id": "SP-1",
        "description": "Bought it on Amazon: https://www.amazon.com/dp/B08FTL2RMH",
        "product_description": "4% Lidocaine Cream",
    }]
    refs = _extract_marketplace_references(incidents)
    assert refs[0]["value"] == "B08FTL2RMH"
    assert refs[0]["type"] == "amazon_asin"
