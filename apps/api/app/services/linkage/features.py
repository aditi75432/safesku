from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

from app.services.linkage.candidates import (
    compact,
    product_tokens,
)


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""

    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def normalized_token_set(value: Any) -> set[str]:
    return product_tokens(value)


def similarity(a: Any, b: Any) -> float:
    left = normalize_text(a)
    right = normalize_text(b)

    if not left or not right:
        return 0.0

    return round(SequenceMatcher(None, left, right).ratio(), 6)


def token_jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return round(len(left & right) / len(union), 6)


def token_coverage(source: set[str], target: set[str]) -> float:
    if not source:
        return 0.0
    return round(len(source & target) / len(source), 6)


@dataclass(frozen=True)
class PairFeatures:
    cpsc_source_record_id: str
    cpsc_recall_number: str | None
    cpsc_recall_date: str | None
    cpsc_product_name: str | None

    saferproducts_source_record_id: str
    incident_date: str | None
    publication_date: str | None

    exact_upc: int
    cpsc_upc_count: int
    incident_has_upc: int

    shared_product_token_count: int
    product_token_jaccard: float
    cpsc_name_token_coverage: float
    incident_name_token_coverage: float

    product_name_substring: int
    product_name_sequence_similarity: float

    product_brand_present: int
    product_model_present: int
    manufacturer_present: int
    retailer_present: int

    incident_brand_in_cpsc_name: int
    incident_model_in_cpsc_name: int
    manufacturer_in_cpsc_name: int

    @property
    def dict(self) -> dict[str, Any]:
        return asdict(self)


def build_pair_features(
    candidate: Any,
    recall: dict[str, Any],
    incident: dict[str, Any],
) -> PairFeatures:
    cpsc_name = str(candidate.cpsc_product_name or "")
    cpsc_tokens = normalized_token_set(cpsc_name)

    incident_product_text = " ".join(
        value
        for value in (
            incident.get("product_brand"),
            incident.get("product_model"),
            incident.get("product_description"),
        )
        if value
    )
    incident_tokens = normalized_token_set(incident_product_text)

    cpsc_upcs = {
        compact(value)
        for value in (recall.get("product_upcs") or [])
        if compact(value)
    }
    incident_upc = compact(incident.get("product_upc"))

    exact_upc = int(
        bool(incident_upc) and incident_upc in cpsc_upcs
    )

    normalized_cpsc_name = normalize_text(cpsc_name)
    normalized_incident_text = normalize_text(incident_product_text)

    incident_brand = normalize_text(incident.get("product_brand"))
    incident_model = compact(incident.get("product_model"))
    manufacturer = normalize_text(incident.get("manufacturer_name"))

    return PairFeatures(
        cpsc_source_record_id=candidate.cpsc_source_record_id,
        cpsc_recall_number=candidate.cpsc_recall_number,
        cpsc_recall_date=candidate.cpsc_recall_date,
        cpsc_product_name=candidate.cpsc_product_name,

        saferproducts_source_record_id=(
            candidate.saferproducts_source_record_id
        ),
        incident_date=candidate.incident_date,
        publication_date=candidate.publication_date,

        exact_upc=exact_upc,
        cpsc_upc_count=len(cpsc_upcs),
        incident_has_upc=int(bool(incident_upc)),

        shared_product_token_count=len(
            cpsc_tokens & incident_tokens
        ),
        product_token_jaccard=token_jaccard(
            cpsc_tokens,
            incident_tokens,
        ),
        cpsc_name_token_coverage=token_coverage(
            cpsc_tokens,
            incident_tokens,
        ),
        incident_name_token_coverage=token_coverage(
            incident_tokens,
            cpsc_tokens,
        ),

        product_name_substring=int(
            bool(normalized_cpsc_name)
            and normalized_cpsc_name in normalized_incident_text
        ),
        product_name_sequence_similarity=similarity(
            cpsc_name,
            incident_product_text,
        ),

        product_brand_present=int(bool(incident_brand)),
        product_model_present=int(bool(incident_model)),
        manufacturer_present=int(bool(manufacturer)),

        retailer_present=int(bool(incident.get("retailer_name"))),

        incident_brand_in_cpsc_name=int(
            bool(incident_brand)
            and incident_brand in normalized_cpsc_name
        ),
        incident_model_in_cpsc_name=int(
            bool(incident_model)
            and incident_model in compact(cpsc_name)
        ),
        manufacturer_in_cpsc_name=int(
            bool(manufacturer)
            and manufacturer in normalized_cpsc_name
        ),
    )
