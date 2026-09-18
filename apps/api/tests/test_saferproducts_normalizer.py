from __future__ import annotations

from app.services.saferproducts.normalizer import normalize_incident


def test_odata_date_uses_platform_independent_parsing() -> None:
    record = {
        "IncidentReportNumber": "TEST-1",
        "IncidentDate": "/Date(1297036800000)/",
        "IncidentReportPublicationDate": "/Date(1301709487243)/",
    }

    incident = normalize_incident(record)

    assert incident.incident_date is not None
    assert incident.incident_date.isoformat() == "2011-02-07"
    assert incident.publication_date is not None
    assert incident.publication_date.isoformat() == "2011-04-02"


def test_out_of_range_odata_date_does_not_reject_record() -> None:
    record = {
        "IncidentReportNumber": "TEST-2",
        # Deliberately far outside Python datetime's supported range.
        "ProductManufacturedDate": "/Date(999999999999999999999)/",
    }

    incident = normalize_incident(record)

    assert incident.source_record_id == "TEST-2"
    assert incident.product_manufactured_date is None


def test_deferred_odata_value_is_ignored() -> None:
    record = {
        "IncidentReportNumber": "TEST-3",
        "Locale": {
            "__deferred": {
                "uri": "https://example.test/IncidentDetails(3)/Locale"
            }
        },
    }

    incident = normalize_incident(record)

    assert incident.locale is None
