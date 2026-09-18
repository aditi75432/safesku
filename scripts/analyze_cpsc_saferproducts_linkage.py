from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[a-z0-9]+")

STOPWORDS = {
    "the", "and", "for", "with", "from", "due", "risk", "serious",
    "injury", "death", "hazard", "sold", "recalls", "recall",
    "product", "products", "model", "number", "brand",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalize_text(value: Any) -> str:
    if value in (None, ""):
        return ""
    
    text = str(value).replace("™", "").replace("®", "")
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[\u2018\u2019\u201c\u201d]", "'", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def tokens(value: Any) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(normalize_text(value))
        if len(token) >= 2 and token not in STOPWORDS
    }


def first_product(recall: dict[str, Any]) -> dict[str, Any]:
    products = recall.get("products") or []
    return products[0] if products else {}


def cpsc_identity_text(recall: dict[str, Any]) -> str:
    product = first_product(recall)
    parts = [
        recall.get("title"),
        product.get("name"),
        product.get("description"),
    ]
    return " ".join(str(part) for part in parts if part)


def incident_identity_text(incident: dict[str, Any]) -> str:
    parts = [
        incident.get("product_brand"),
        incident.get("product_model"),
        incident.get("product_description"),
        incident.get("manufacturer_name"),
        incident.get("retailer_name"),
    ]
    return " ".join(str(part) for part in parts if part)


def exact_upc_links(
    recalls: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
) -> dict[str, list[str]]:
    incident_by_upc: defaultdict[str, list[str]] = defaultdict(list)

    for incident in incidents:
        upc = normalize_text(incident.get("product_upc"))
        if upc:
            incident_by_upc[upc].append(incident["source_record_id"])

    links: dict[str, list[str]] = {}

    for recall in recalls:
        recall_id = recall["source_record_id"]
        upcs = [
            normalize_text(upc)
            for upc in (recall.get("product_upcs") or [])
            if normalize_text(upc)
        ]

        matched_ids = []
        for upc in upcs:
            matched_ids.extend(incident_by_upc.get(upc, []))

        if matched_ids:
            links[recall_id] = sorted(set(matched_ids))

    return links


def build_inverted_index(
    incidents: list[dict[str, Any]],
) -> dict[str, set[str]]:
    index: defaultdict[str, set[str]] = defaultdict(set)

    for incident in incidents:
        incident_id = incident["source_record_id"]
        for token in tokens(incident_identity_text(incident)):
            index[token].add(incident_id)

    return dict(index)


def candidate_stats(
    recalls: list[dict[str, Any]],
    incidents_by_id: dict[str, dict[str, Any]],
    inverted_index: dict[str, set[str]],
) -> dict[str, Any]:
    candidate_counts: list[int] = []
    recalls_with_candidates = 0
    top_candidates: list[dict[str, Any]] = []

    for recall in recalls:
        recall_tokens = tokens(cpsc_identity_text(recall))

        candidate_ids: set[str] = set()
        for token in recall_tokens:
            candidate_ids.update(inverted_index.get(token, set()))

        if not candidate_ids:
            candidate_counts.append(0)
            continue

        recalls_with_candidates += 1
        candidate_counts.append(len(candidate_ids))

        scored: list[tuple[float, str, int]] = []

        for incident_id in candidate_ids:
            incident_tokens = tokens(
                incident_identity_text(incidents_by_id[incident_id])
            )

            overlap = len(recall_tokens & incident_tokens)
            union = len(recall_tokens | incident_tokens)

            if union == 0:
                continue

            jaccard = overlap / union
            scored.append((jaccard, incident_id, overlap))

        scored.sort(reverse=True)

        for score, incident_id, overlap in scored[:3]:
            top_candidates.append(
                {
                    "cpsc_source_record_id": recall["source_record_id"],
                    "cpsc_recall_number": recall.get("recall_number"),
                    "cpsc_title": recall.get("title"),
                    "saferproducts_source_record_id": incident_id,
                    "token_jaccard": round(score, 4),
                    "shared_identity_tokens": overlap,
                    "incident_product_brand": incidents_by_id[
                        incident_id
                    ].get("product_brand"),
                    "incident_product_model": incidents_by_id[
                        incident_id
                    ].get("product_model"),
                }
            )

    distribution = Counter(candidate_counts)

    return {
        "recalls_with_at_least_one_token_candidate": recalls_with_candidates,
        "candidate_count_min": min(candidate_counts, default=0),
        "candidate_count_max": max(candidate_counts, default=0),
        "candidate_count_median": (
            sorted(candidate_counts)[len(candidate_counts) // 2]
            if candidate_counts
            else 0
        ),
        "candidate_count_distribution_top_15": {
            str(k): v
            for k, v in distribution.most_common(15)
        },
        "top_candidates_sample": top_candidates[:30],
    }


def main() -> None:
    cpsc_path = Path("data/benchmark/cpsc/recalls.jsonl")
    incident_path = Path("data/benchmark/saferproducts/incidents.jsonl")
    output_path = Path("data/benchmark/linkage/linkage_audit.json")

    recalls = load_jsonl(cpsc_path)
    incidents = load_jsonl(incident_path)

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }

    cpsc_upc_count = sum(
        bool(recall.get("product_upcs"))
        for recall in recalls
    )
    incident_upc_count = sum(
        bool(incident.get("product_upc"))
        for incident in incidents
    )

    cpsc_product_name_count = sum(
        bool(first_product(recall).get("name"))
        for recall in recalls
    )
    cpsc_product_description_count = sum(
        bool(first_product(recall).get("description"))
        for recall in recalls
    )

    incident_fields = {
        field: sum(bool(incident.get(field)) for incident in incidents)
        for field in (
            "product_brand",
            "product_model",
            "product_description",
            "product_category",
            "product_upc",
            "manufacturer_name",
            "retailer_name",
        )
    }

    upc_links = exact_upc_links(recalls, incidents)
    inverted_index = build_inverted_index(incidents)

    token_stats = candidate_stats(
        recalls,
        incidents_by_id,
        inverted_index,
    )

    report = {
        "recall_count": len(recalls),
        "incident_count": len(incidents),
        "cpsc_identity_field_coverage": {
            "product_name": cpsc_product_name_count,
            "product_description": cpsc_product_description_count,
            "recall_upc": cpsc_upc_count,
        },
        "saferproducts_identity_field_coverage": incident_fields,
        "exact_upc_link": {
            "recalls_with_exact_upc_incident_match": len(upc_links),
            "sample_links": [
                {
                    "cpsc_source_record_id": recall_id,
                    "saferproducts_source_record_ids": incident_ids,
                }
                for recall_id, incident_ids in list(upc_links.items())[:20]
            ],
        },
        "token_candidate_analysis": token_stats,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU CPSC ↔ SaferProducts linkage audit")
    print("-------------------------------------------")
    print(f"CPSC recalls: {len(recalls)}")
    print(f"SaferProducts incidents: {len(incidents)}")
    print(
        "CPSC products with name: "
        f"{cpsc_product_name_count}/{len(recalls)}"
    )
    print(
        "CPSC recalls with UPC: "
        f"{cpsc_upc_count}/{len(recalls)}"
    )
    print(
        "SaferProducts incidents with brand: "
        f"{incident_fields['product_brand']}/{len(incidents)}"
    )
    print(
        "SaferProducts incidents with model: "
        f"{incident_fields['product_model']}/{len(incidents)}"
    )
    print(
        "SaferProducts incidents with UPC: "
        f"{incident_upc_count}/{len(incidents)}"
    )
    print(
        "Exact CPSC UPC -> incident links: "
        f"{len(upc_links)} recalls"
    )
    print(
        "Recalls with >=1 token candidate: "
        f"{token_stats['recalls_with_at_least_one_token_candidate']}"
    )
    print(
        "Candidate count range: "
        f"{token_stats['candidate_count_min']} -> "
        f"{token_stats['candidate_count_max']}"
    )
    print(f"Audit: {output_path}")


if __name__ == "__main__":
    main()
