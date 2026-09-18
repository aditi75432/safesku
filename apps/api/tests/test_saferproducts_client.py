from __future__ import annotations

from app.services.saferproducts.client import SaferProductsClient


def test_parse_odata_v3_page_returns_page_object() -> None:
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
    assert page.raw_payload == payload
