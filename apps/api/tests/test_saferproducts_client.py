from __future__ import annotations

from app.services.saferproducts.client import SaferProductsClient
from app.services.saferproducts.normalizer import normalize_incident


def test_parse_odata_v3_page() -> None:
    payload = {
        "d": {
            "__count": "123",
            "results": [
                {
                    "IncidentReportNumber": "20200101-TEST",
                    "IncidentDate": "1/2/2020",
                }
            ],
            "__next": "https://example.test/next",
        }
    }

    page = SaferProductsClient._parse_page(payload)

    assert len(page.records) == 1
    assert page.records[0]["IncidentReportNumber"] == "20200101-TEST"
    assert page.next_url == "https://example.test/next"
    assert page.total_count == 123


def test_normalize_incident() -> None:
    record = {
        "IncidentReportNumber": "20200101-TEST",
        "IncidentDate": "2020-01-02",
        "IncidentReportPublicationDate": "2020-01-10",
        "IncidentDescription": "Product overheated.",
        "ProductBrandName": "Example",
        "ProductModelName": "X100",
        "RetailCompanyName": "Example Store",
    }

    incident = normalize_incident(record)

    assert incident.source == "saferproducts"
    assert incident.source_record_id == "20200101-TEST"
    assert incident.incident_date is not None
    assert incident.incident_date.isoformat() == "2020-01-02"
    assert incident.product_brand == "Example"
    assert incident.product_model == "X100"
