from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Iterable

from app.models.safety_incident import SafetyIncident


_ODATA_DATE_RE = re.compile(r"^/Date\((?P<ms>-?\d+)(?P<offset>[+-]\d{4})?\)/$")


def _first(record: dict[str, Any], names: Iterable[str]) -> Any:
    for name in names:
        value = record.get(name)
        if value not in (None, ""):
            return value
    return None


def _scalar(value: Any) -> Any:
    """Return primitive values and ignore OData navigation/deferred objects."""
    if value in (None, ""):
        return None

    if isinstance(value, (str, int, float, bool, datetime, date)):
        return value

    if isinstance(value, dict):
        # OData v3 navigation properties can be represented as:
        # {"__deferred": {"uri": "..."}}
        return None

    return None


def _text(value: Any) -> str | None:
    value = _scalar(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_date(value: Any) -> date | None:
    value = _scalar(value)

    if value is None:
        return None

    if isinstance(value, date) and not isinstance(value, datetime):
        return value

    if isinstance(value, datetime):
        return value.date()

    text = str(value).strip()

    match = _ODATA_DATE_RE.match(text)
    if match:
        milliseconds = int(match.group("ms"))
        return datetime.fromtimestamp(
            milliseconds / 1000,
            tz=timezone.utc,
        ).date()

    for candidate in (text[:10], text):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            pass

    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass

    return None


def normalize_incident(record: dict[str, Any]) -> SafetyIncident:
    """Map live SaferProducts OData scalar properties to SafeSKU."""
    source_id = _first(
        record,
        (
            "IncidentReportNumber",
            "IncidentReportNo",
            "ReportNumber",
            "ReportId",
            "IncidentID",
            "Id",
        ),
    )

    if source_id is None:
        raise ValueError("SaferProducts record has no usable incident identifier.")

    return SafetyIncident(
        source_record_id=_text(source_id) or "",
        incident_date=_parse_date(
            _first(record, ("IncidentDate", "IncidentDateTime"))
        ),
        publication_date=_parse_date(
            _first(
                record,
                (
                    "IncidentReportPublicationDate",
                    "ReportFirstPublicationDate",
                    "PublicationDate",
                ),
            )
        ),
        incident_description=_text(
            _first(record, ("IncidentDescription", "Description"))
        ),
        incident_location=_text(_first(record, ("IncidentLocation",))),
        locale=_text(_first(record, ("Locale",))),
        product_brand=_text(
            _first(record, ("ProductBrandName", "ProductBrand"))
        ),
        product_model=_text(
            _first(record, ("ProductModelName", "ProductModel"))
        ),
        product_description=_text(
            _first(
                record,
                (
                    "IncidentProductDescription",
                    "ProductDescription",
                ),
            )
        ),
        product_category=_text(_first(record, ("ProductCategory",))),
        product_upc=_text(
            _first(record, ("ProductUPCCode", "ProductUPC"))
        ),
        product_serial_number=_text(
            _first(record, ("ProductSerialNumber",))
        ),
        product_manufactured_date=_parse_date(
            _first(record, ("ProductManufacturedDate",))
        ),
        product_purchased_date=_parse_date(
            _first(record, ("ProductPurchasedDate",))
        ),
        manufacturer_name=_text(
            _first(
                record,
                (
                    "ProductManufacturerName",
                    "ManufacturerName",
                    "Manufacturer",
                ),
            )
        ),
        manufacturer_location=_text(
            _first(record, ("ManufacturerLocation",))
        ),
        manufacturer_notification_date=_parse_date(
            _first(record, ("ManufacturerNotificationDate",))
        ),
        manufacturer_comments=_text(
            _first(
                record,
                (
                    "CompanyComments",
                    "ManufacturerComments",
                ),
            )
        ),
        retailer_name=_text(
            _first(
                record,
                (
                    "ProductRetailCompanyName",
                    "RetailCompanyName",
                    "RetailerName",
                    "RetailCompany",
                ),
            )
        ),
        retailer_location=_text(
            _first(
                record,
                (
                    "RetailCompanyLocation",
                    "RetailerLocation",
                ),
            )
        ),
    )
