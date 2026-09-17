from __future__ import annotations
from datetime import date, datetime
from typing import Any
from app.models.recall import RecallFirm, RecallHazard, RecallProduct, RecallRecord, RecallRemedy, RecallRemedyOption

def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

def _nested_items(record: dict[str, Any], group: str, item: str) -> list[dict[str, Any]]:
    value = record.get(group)
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        nested = value.get(item)
        if isinstance(nested, list):
            return [x for x in nested if isinstance(x, dict)]
        if isinstance(nested, dict):
            return [nested]
        return [value]
    return []

def _parse_date(value: Any) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None

def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

def normalize_recall(record: dict[str, Any]) -> RecallRecord:
    source_id = _text(record.get("RecallID"))
    if not source_id:
        raise ValueError("CPSC record is missing RecallID")

    products = [
        RecallProduct(
            name=_text(item.get("Name")),
            description=_text(item.get("Description")),
            model=_text(item.get("Model")),
            type=_text(item.get("Type")),
            category_id=_text(item.get("CategoryID")),
            number_of_units=item.get("NumberOfUnits"),
        )
        for item in _nested_items(record, "Products", "Product")
    ]

    def firms(group: str, item_name: str) -> list[RecallFirm]:
        return [
            RecallFirm(name=_text(item.get("Name")), company_id=_text(item.get("CompanyID")))
            for item in _nested_items(record, group, item_name)
        ]

    hazards = [
        RecallHazard(
            name=_text(item.get("Name")),
            hazard_type=_text(item.get("HazardType")),
            hazard_type_id=_text(item.get("HazardTypeID")),
        )
        for item in _nested_items(record, "Hazards", "Hazard")
    ]

    remedies = [RecallRemedy(name=_text(i.get("Name"))) for i in _nested_items(record, "Remedies", "Remedy")]
    remedy_options = [RecallRemedyOption(option=_text(i.get("Option"))) for i in _nested_items(record, "RemedyOptions", "RemedyOption")]
    injuries = [_text(i.get("Name")) for i in _nested_items(record, "Injuries", "Injury") if _text(i.get("Name"))]
    countries = [_text(i.get("Country")) for i in _nested_items(record, "ManufacturerCountries", "ManufacturerCountry") if _text(i.get("Country"))]
    upcs = [_text(i.get("UPC")) for i in _nested_items(record, "ProductUPCs", "ProductUPC") if _text(i.get("UPC"))]

    return RecallRecord(
        source_record_id=source_id,
        recall_number=_text(record.get("RecallNumber")),
        recall_date=_parse_date(record.get("RecallDate")),
        last_publish_date=_parse_datetime(record.get("LastPublishDate")),
        title=_text(record.get("Title")),
        description=_text(record.get("Description")),
        url=_text(record.get("URL")),
        consumer_contact=_text(record.get("ConsumerContact")),
        products=products,
        injuries=injuries,
        manufacturers=firms("Manufacturers", "Manufacturer"),
        retailers=firms("Retailers", "Retailer"),
        importers=firms("Importers", "Importer"),
        distributors=firms("Distributors", "Distributor"),
        manufacturer_countries=countries,
        product_upcs=upcs,
        hazards=hazards,
        remedies=remedies,
        remedy_options=remedy_options,
    )
