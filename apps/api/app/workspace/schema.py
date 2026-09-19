from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


SOURCE_TYPES = {
    "cpsc",
    "saferproducts",
    "amazon_products",
    "amazon_reviews",
    "linkage",
}


@dataclass(frozen=True)
class CanonicalRow:
    source_type: str
    values: dict[str, Any]


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"none", "null", "nan"} else text


def _first(row: Mapping[str, Any], *names: str) -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value not in (None, ""):
            return value
    return ""


def detect_source(headers: set[str], filename: str, source_hint: str | None = None) -> str:
    if source_hint:
        hint = source_hint.strip().lower()
        aliases = {
            "amazon": "amazon_products",
            "amazon_product": "amazon_products",
            "amazon_metadata": "amazon_products",
            "reviews": "amazon_reviews",
            "safer": "saferproducts",
            "saferproducts.gov": "saferproducts",
            "candidate": "linkage",
        }
        hint = aliases.get(hint, hint)
        if hint in SOURCE_TYPES:
            return hint

    names = {h.lower() for h in headers}
    lower_name = filename.lower()

    if {"recall_number", "recall_date"} <= names or "cpsc" in lower_name:
        return "cpsc"
    if {"incident_date", "publication_date"} <= names or "saferproducts" in lower_name or "safer" in lower_name:
        return "saferproducts"
    if {"cpsc_recall_number", "amazon_parent_asin"} <= names or "linkage" in lower_name or "candidate" in lower_name:
        return "linkage"
    if {"rating", "text"} <= names or {"rating", "review_text"} <= names:
        return "amazon_reviews"
    if "parent_asin" in names or "amazon_parent_asin" in names or "parent_asin" in lower_name:
        return "amazon_products"

    raise ValueError(
        "Could not identify the dataset. Use the Source selector in the UI or pass a source hint "
        "of cpsc, saferproducts, amazon_products, amazon_reviews, or linkage."
    )


def canonicalize(source_type: str, row: Mapping[str, Any]) -> CanonicalRow:
    """Map common source formats into SafeSKU's small canonical contract."""
    if source_type == "cpsc":
        values = {
            "source_record_id": _clean(_first(row, "source_record_id", "cpsc_source_record_id", "id", "record_id")),
            "recall_number": _clean(_first(row, "recall_number", "cpsc_recall_number", "recallnumber")),
            "recall_date": _clean(_first(row, "recall_date", "cpsc_recall_date", "date")),
            "product_name": _clean(_first(row, "product_name", "cpsc_product_name", "product")),
            "title": _clean(_first(row, "title", "cpsc_title", "description")),
            "hazards": _first(row, "hazards", "cpsc_hazards", "hazard"),
            "description": _clean(_first(row, "description", "cpsc_description")),
            "url": _clean(_first(row, "url", "cpsc_url", "recall_url")),
            "brand": _clean(_first(row, "brand", "product_brand")),
            "model": _clean(_first(row, "model", "product_model", "model_number")),
            "upc": _clean(_first(row, "upc", "product_upc")),
            "category": _clean(_first(row, "category", "product_category", "category_id")),
        }
        if not values["source_record_id"]:
            values["source_record_id"] = f"cpsc-{values['recall_number']}"
        return CanonicalRow(source_type, values)

    if source_type == "saferproducts":
        values = {
            "source_record_id": _clean(_first(row, "source_record_id", "saferproducts_source_record_id", "incident_id", "id")),
            "incident_date": _clean(_first(row, "incident_date", "date_of_incident")),
            "publication_date": _clean(_first(row, "publication_date", "published_date", "date_published")),
            "brand": _clean(_first(row, "product_brand", "brand", "incident_brand")),
            "model": _clean(_first(row, "product_model", "model", "incident_model")),
            "upc": _clean(_first(row, "product_upc", "upc", "incident_upc")),
            "product_description": _clean(_first(row, "product_description", "product", "incident_product_description")),
            "description": _clean(_first(row, "incident_description", "description", "comments")),
            "manufacturer": _clean(_first(row, "manufacturer_name", "manufacturer", "incident_manufacturer")),
            "retailer": _clean(_first(row, "retailer_name", "retailer", "incident_retailer")),
            "recall_number": _clean(_first(row, "cpsc_recall_number", "recall_number", "recallnumber")),
        }
        if not values["source_record_id"]:
            raise ValueError("SaferProducts record is missing an incident identifier")
        return CanonicalRow(source_type, values)

    if source_type == "amazon_products":
        values = {
            "parent_asin": _clean(_first(row, "parent_asin", "amazon_parent_asin", "parentAsin")),
            "title": _clean(_first(row, "title", "amazon_title", "product_title")),
            "brand": _clean(_first(row, "brand", "amazon_brand")),
            "model": _clean(_first(row, "model", "model_number", "modelNumber", "amazon_model")),
            "upc": _clean(_first(row, "upc", "product_upc", "barcode", "gtin")),
            "manufacturer": _clean(_first(row, "manufacturer", "amazon_manufacturer")),
            "category": _clean(_first(row, "category", "main_category", "category_name", "amazon_category")),
        }
        if not values["parent_asin"]:
            values["parent_asin"] = _clean(_first(row, "asin"))
        if not values["parent_asin"]:
            raise ValueError("Amazon product record is missing parent_asin/asin")
        return CanonicalRow(source_type, values)

    if source_type == "amazon_reviews":
        values = {
            "review_id": _clean(_first(row, "review_id", "id")),
            "asin": _clean(_first(row, "asin", "parent_asin", "parentAsin")),
            "parent_asin": _clean(_first(row, "parent_asin", "parentAsin", "asin")),
            "rating": _clean(_first(row, "rating", "stars", "score")),
            "review_title": _clean(_first(row, "title", "review_title")),
            "review_text": _clean(_first(row, "text", "review_text", "review_body")),
            "review_date": _clean(_first(row, "timestamp", "review_date", "date")),
            "verified_purchase": _clean(_first(row, "verified_purchase", "verified", "verifiedPurchase")),
        }
        if not values["asin"]:
            raise ValueError("Amazon review record is missing asin/parent_asin")
        if not values["review_id"]:
            values["review_id"] = f"{values['asin']}:{values['review_date']}:{values['review_title'][:40]}"
        return CanonicalRow(source_type, values)

    if source_type == "linkage":
        values = {
            "recall_number": _clean(_first(row, "cpsc_recall_number", "recall_number")),
            "parent_asin": _clean(_first(row, "amazon_parent_asin", "parent_asin", "asin")),
            "title": _clean(_first(row, "amazon_title", "title")),
            "brand": _clean(_first(row, "amazon_brand", "brand")),
            "model": _clean(_first(row, "amazon_model", "model")),
            "upc": _clean(_first(row, "amazon_upc", "upc")),
            "exact_upc": int(float(_first(row, "exact_upc") or 0)),
            "shared_product_token_count": int(float(_first(row, "shared_product_token_count") or 0)),
            "product_token_jaccard": float(_first(row, "product_token_jaccard") or 0),
            "product_name_sequence_similarity": float(_first(row, "product_name_sequence_similarity") or 0),
            "brand_relation": _clean(_first(row, "brand_relation")),
            "blocking_sources": _clean(_first(row, "blocking_sources")),
            "review_label": _clean(_first(row, "review_label", "label")),
        }
        if not values["recall_number"] or not values["parent_asin"]:
            raise ValueError("Linkage record requires recall_number and parent_asin")
        return CanonicalRow(source_type, values)

    raise ValueError(f"Unsupported source type: {source_type}")
