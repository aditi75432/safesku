from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "and", "for", "with", "from", "due", "risk", "serious",
    "injury", "death", "hazard", "sold", "recalls", "recall",
    "product", "products", "model", "number", "this", "that",
    "inc", "llc", "corp", "corporation", "company", "manufactured",
    "unit", "units", "including", "included", "new", "used",
}


@dataclass(frozen=True)
class CandidatePair:
    cpsc_source_record_id: str
    cpsc_recall_number: str | None
    cpsc_recall_date: str | None
    cpsc_product_name: str | None
    saferproducts_source_record_id: str

    blocking_sources: tuple[str, ...]
    exact_upc: bool
    shared_product_tokens: tuple[str, ...]
    shared_product_token_count: int
    product_token_jaccard: float

    incident_date: str | None
    publication_date: str | None
    incident_brand: str | None
    incident_model: str | None
    incident_upc: str | None
    incident_product_description: str | None


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""

    text = unicodedata.normalize("NFKC", str(value)).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", normalize_text(value))


def product_tokens(value: Any) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(normalize_text(value))
        if len(token) >= 3 and token not in STOPWORDS
    }


def first_product(recall: dict[str, Any]) -> dict[str, Any]:
    products = recall.get("products") or []
    return products[0] if products else {}


def recall_product_name(recall: dict[str, Any]) -> str:
    return normalize_text(first_product(recall).get("name"))


def recall_product_upcs(recall: dict[str, Any]) -> set[str]:
    return {
        compact(value)
        for value in (recall.get("product_upcs") or [])
        if compact(value)
    }


def incident_identity_tokens(incident: dict[str, Any]) -> set[str]:
    values = (
        incident.get("product_brand"),
        incident.get("product_model"),
        incident.get("product_description"),
    )

    result: set[str] = set()

    for value in values:
        result.update(product_tokens(value))

    return result


def build_upc_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        upc = compact(incident.get("product_upc"))

        if upc:
            index[upc].add(incident["source_record_id"])

    return dict(index)


def build_token_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        incident_id = incident["source_record_id"]

        for token in incident_identity_tokens(incident):
            index[token].add(incident_id)

    return dict(index)


def generate_candidates(
    recall: dict[str, Any],
    incidents_by_id: dict[str, dict[str, Any]],
    upc_index: dict[str, set[str]],
    token_index: dict[str, set[str]],
) -> list[CandidatePair]:
    """Generate auditable candidates using the locked blocking union.

    A candidate enters the set when either:
      1. an exact UPC matches, or
      2. at least two tokens from the CPSC product name occur in the
         SaferProducts product identity fields.
    """
    product_name = recall_product_name(recall)
    recall_tokens = product_tokens(product_name)
    recall_upcs = recall_product_upcs(recall)

    upc_candidates: set[str] = set()

    for upc in recall_upcs:
        upc_candidates.update(upc_index.get(upc, set()))

    token_overlap: Counter[str] = Counter()

    for token in recall_tokens:
        for incident_id in token_index.get(token, set()):
            token_overlap[incident_id] += 1

    token_candidates = {
        incident_id
        for incident_id, overlap in token_overlap.items()
        if overlap >= 2
    }

    candidate_ids = upc_candidates | token_candidates
    candidates: list[CandidatePair] = []

    for incident_id in candidate_ids:
        incident = incidents_by_id[incident_id]
        incident_tokens = incident_identity_tokens(incident)

        shared_tokens = tuple(
            sorted(recall_tokens & incident_tokens)
        )

        union_size = len(recall_tokens | incident_tokens)

        jaccard = (
            len(shared_tokens) / union_size
            if union_size
            else 0.0
        )

        sources: list[str] = []

        if incident_id in upc_candidates:
            sources.append("exact_upc")

        if incident_id in token_candidates:
            sources.append("shared_2plus_product_tokens")

        candidates.append(
            CandidatePair(
                cpsc_source_record_id=recall["source_record_id"],
                cpsc_recall_number=recall.get("recall_number"),
                cpsc_recall_date=recall.get("recall_date"),
                cpsc_product_name=first_product(recall).get("name"),
                saferproducts_source_record_id=incident_id,
                blocking_sources=tuple(sources),
                exact_upc=incident_id in upc_candidates,
                shared_product_tokens=shared_tokens,
                shared_product_token_count=len(shared_tokens),
                product_token_jaccard=round(jaccard, 6),
                incident_date=incident.get("incident_date"),
                publication_date=incident.get("publication_date"),
                incident_brand=incident.get("product_brand"),
                incident_model=incident.get("product_model"),
                incident_upc=incident.get("product_upc"),
                incident_product_description=incident.get(
                    "product_description"
                ),
            )
        )

    candidates.sort(
        key=lambda candidate: (
            1 if candidate.exact_upc else 0,
            candidate.shared_product_token_count,
            candidate.product_token_jaccard,
            candidate.saferproducts_source_record_id,
        ),
        reverse=True,
    )

    return candidates
