from __future__ import annotations

from app.services.saferproducts.normalizer import normalize_incident


def test_normalize_live_saferproducts_fields() -> None:
    record = {
        "IncidentReportNumber": "20200101-TEST",
        "IncidentDate": "1/2/2020",
        "IncidentReportPublicationDate": "1/10/2020",
        "IncidentDescription": "Product overheated.",
        "ProductBrandName": "Example",
        "ProductModelName": "X100",
        "IncidentProductDescription": "Example product",
        "ProductCategory": "Kitchen",
        "ProductUPCCode": "012345678901",
        "ProductManufacturerName": "Example Manufacturer",
        "ProductRetailCompanyName": "Example Store",
    }

    incident = normalize_incident(record)

    assert incident.source_record_id == "20200101-TEST"
    assert incident.incident_date is not None
    assert incident.incident_date.isoformat() == "2020-01-02"
    assert incident.publication_date is not None
    assert incident.publication_date.isoformat() == "2020-01-10"
    assert incident.product_category == "Kitchen"
    assert incident.product_upc == "012345678901"
    assert incident.manufacturer_name == "Example Manufacturer"
    assert incident.retailer_name == "Example Store"


def test_normalize_odata_millisecond_date() -> None:
    record = {
        "IncidentReportNumber": "20200101-TEST",
        "IncidentDate": "/Date(1577923200000)/",
    }

    incident = normalize_incident(record)

    assert incident.incident_date is not None
    assert incident.incident_date.isoformat() == "2020-01-02"


def test_deferred_navigation_property_is_ignored() -> None:
    record = {
        "IncidentReportNumber": "20200101-TEST",
        "Locale": {
            "__deferred": {
                "uri": "https://example.test/IncidentDetails(1)/Locale"
            }
        },
    }

    incident = normalize_incident(record)

    assert incident.locale is None
