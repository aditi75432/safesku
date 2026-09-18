from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_INPUT = Path("data/benchmark/linkage/feature_review.jsonl")
DEFAULT_CANDIDATES = Path("data/benchmark/linkage/candidate_review.jsonl")
DEFAULT_RECALLS = Path("data/benchmark/cpsc/recalls.jsonl")
DEFAULT_INCIDENTS = Path("data/benchmark/saferproducts/incidents.jsonl")
DEFAULT_JSONL = Path("data/benchmark/linkage/human_review_set.jsonl")
DEFAULT_CSV = Path("data/benchmark/linkage/human_review_set.csv")
DEFAULT_MANIFEST = Path("data/benchmark/linkage/human_review_set_manifest.json")
LABELS = ("MATCH", "NON_MATCH", "UNCERTAIN")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def temporal_status(row: dict[str, Any]) -> str:
    recall_date = row.get("cpsc_recall_date")
    incident_date = row.get("incident_date")
    publication_date = row.get("publication_date")

    if not recall_date or not incident_date or not publication_date:
        return "unknown"
    if incident_date >= recall_date:
        return "incident_on_or_after_recall"
    if publication_date >= recall_date:
        return "pre_incident_published_after_recall"
    return "pre_recall_public"


def similarity_band(value: float) -> str:
    if value >= 0.70:
        return "high"
    if value >= 0.40:
        return "medium"
    return "low"


def jaccard_band(value: float) -> str:
    if value >= 0.40:
        return "high"
    if value >= 0.15:
        return "medium"
    return "low"


def candidate_strength(row: dict[str, Any]) -> tuple[int, float, float, int]:
    return (
        int(row.get("exact_upc", 0)),
        float(row.get("product_token_jaccard", 0.0)),
        float(row.get("product_name_sequence_similarity", 0.0)),
        int(row.get("shared_product_token_count", 0)),
    )


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row["cpsc_source_record_id"]),
        str(row["saferproducts_source_record_id"]),
    )


def shuffled(rows: list[dict[str, Any]], rng: random.Random) -> list[dict[str, Any]]:
    result = list(rows)
    rng.shuffle(result)
    return result


def take_from_stratum(
    pool: list[dict[str, Any]],
    count: int,
    selected: dict[tuple[str, str], dict[str, Any]],
    per_recall_cap: int,
    rng: random.Random,
) -> int:
    added = 0
    per_recall = Counter(row["cpsc_source_record_id"] for row in selected.values())
    ordered = shuffled(pool, rng)
    ordered.sort(key=candidate_strength, reverse=True)

    for row in ordered:
        if added >= count:
            break
        key = row_key(row)
        recall_id = row["cpsc_source_record_id"]
        if key in selected or per_recall[recall_id] >= per_recall_cap:
            continue
        selected[key] = row
        per_recall[recall_id] += 1
        added += 1
    return added


def choose_review_rows(
    rows: list[dict[str, Any]],
    sample_size: int,
    per_recall_cap: int,
    seed: int,
) -> list[dict[str, Any]]:
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    if per_recall_cap <= 0:
        raise ValueError("per_recall_cap must be positive")

    rng = random.Random(seed)
    selected: dict[tuple[str, str], dict[str, Any]] = {}

    seeds = [row for row in rows if row.get("initial_label") == "positive_seed"]
    for row in sorted(seeds, key=row_key):
        selected[row_key(row)] = row

    if len(selected) > sample_size:
        raise ValueError(
            f"sample_size {sample_size} is smaller than the {len(selected)} UPC seeds"
        )

    non_upc = [row for row in rows if row.get("initial_label") != "positive_seed"]

    pre_recall = [row for row in non_upc if temporal_status(row) == "pre_recall_public"]
    high = [
        row for row in non_upc
        if float(row.get("product_name_sequence_similarity", 0.0)) >= 0.70
        or float(row.get("product_token_jaccard", 0.0)) >= 0.40
    ]
    medium = [
        row for row in non_upc
        if row not in high
        and (
            float(row.get("product_name_sequence_similarity", 0.0)) >= 0.40
            or float(row.get("product_token_jaccard", 0.0)) >= 0.15
        )
    ]
    two_token = [
        row for row in non_upc if int(row.get("shared_product_token_count", 0)) == 2
    ]
    low = [row for row in non_upc if row not in high and row not in medium]

    strata = [
        ("pre_recall_public", pre_recall, 30),
        ("high_similarity", high, 35),
        ("medium_similarity", medium, 30),
        ("two_shared_tokens", two_token, 25),
        ("low_similarity", low, 20),
    ]

    for _, pool, target in strata:
        remaining = sample_size - len(selected)
        if remaining <= 0:
            break
        take_from_stratum(pool, min(target, remaining), selected, per_recall_cap, rng)

    remaining = sample_size - len(selected)
    if remaining > 0:
        take_from_stratum(non_upc, remaining, selected, per_recall_cap, rng)

    chosen = list(selected.values())
    chosen.sort(
        key=lambda row: (
            0 if row.get("initial_label") == "positive_seed" else 1,
            row["cpsc_source_record_id"],
            row["saferproducts_source_record_id"],
        )
    )
    return chosen


def join_source_evidence(
    selected: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
    recalls: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_by_key = {row_key(row): row for row in candidates}
    recalls_by_id = {row["source_record_id"]: row for row in recalls}
    incidents_by_id = {row["source_record_id"]: row for row in incidents}

    enriched: list[dict[str, Any]] = []
    missing_candidates = 0
    missing_recalls = 0
    missing_incidents = 0

    for row in selected:
        key = row_key(row)
        candidate = candidate_by_key.get(key)
        recall = recalls_by_id.get(row["cpsc_source_record_id"])
        incident = incidents_by_id.get(row["saferproducts_source_record_id"])

        if candidate is None:
            missing_candidates += 1
        if recall is None:
            missing_recalls += 1
        if incident is None:
            missing_incidents += 1

        merged = dict(row)
        if candidate:
            for field in (
                "blocking_sources",
                "selection_reason",
                "review_rank",
                "incident_brand",
                "incident_model",
                "incident_upc",
                "incident_product_description",
                "incident_date",
                "publication_date",
            ):
                if merged.get(field) in (None, "", [], {}):
                    merged[field] = candidate.get(field)

        if recall:
            merged.update(
                {
                    "cpsc_title": recall.get("title"),
                    "cpsc_description": recall.get("description"),
                    "cpsc_hazards": recall.get("hazards"),
                    "cpsc_manufacturers": recall.get("manufacturers"),
                    "cpsc_retailers": recall.get("retailers"),
                    "cpsc_url": recall.get("url"),
                }
            )

        if incident:
            merged.update(
                {
                    "incident_description": incident.get("incident_description"),
                    "incident_category": incident.get("product_category"),
                    "incident_manufacturer": incident.get("manufacturer_name"),
                    "incident_retailer": incident.get("retailer_name"),
                    "incident_locale": incident.get("locale"),
                    "incident_product_purchased_date": incident.get("product_purchased_date"),
                    "incident_product_manufactured_date": incident.get("product_manufactured_date"),
                    "incident_manufacturer_comments": incident.get("manufacturer_comments"),
                    "incident_user_still_has_product": incident.get("user_still_has_product"),
                    "incident_severity": incident.get("severity_type_id"),
                }
            )

        merged["evidence_join_status"] = {
            "candidate": candidate is not None,
            "recall": recall is not None,
            "incident": incident is not None,
        }
        enriched.append(merged)

    if missing_candidates or missing_recalls or missing_incidents:
        raise ValueError(
            "Source join incomplete: "
            f"missing candidate={missing_candidates}, "
            f"recall={missing_recalls}, "
            f"incident={missing_incidents}"
        )

    return enriched


def prepare_output_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for index, row in enumerate(rows, start=1):
        output.append(
            {
                "review_id": f"ER-{index:04d}",
                "cpsc_source_record_id": row["cpsc_source_record_id"],
                "cpsc_recall_number": row.get("cpsc_recall_number"),
                "cpsc_recall_date": row.get("cpsc_recall_date"),
                "cpsc_product_name": row.get("cpsc_product_name"),
                "cpsc_title": row.get("cpsc_title"),
                "cpsc_description": row.get("cpsc_description"),
                "cpsc_hazards": row.get("cpsc_hazards"),
                "cpsc_manufacturers": row.get("cpsc_manufacturers"),
                "cpsc_retailers": row.get("cpsc_retailers"),
                "cpsc_url": row.get("cpsc_url"),
                "saferproducts_source_record_id": row["saferproducts_source_record_id"],
                "incident_date": row.get("incident_date"),
                "publication_date": row.get("publication_date"),
                "incident_brand": row.get("incident_brand"),
                "incident_model": row.get("incident_model"),
                "incident_upc": row.get("incident_upc"),
                "incident_product_description": row.get("incident_product_description"),
                "incident_description": row.get("incident_description"),
                "incident_category": row.get("incident_category"),
                "incident_manufacturer": row.get("incident_manufacturer"),
                "incident_retailer": row.get("incident_retailer"),
                "incident_locale": row.get("incident_locale"),
                "incident_product_purchased_date": row.get("incident_product_purchased_date"),
                "incident_product_manufactured_date": row.get("incident_product_manufactured_date"),
                "incident_manufacturer_comments": row.get("incident_manufacturer_comments"),
                "incident_user_still_has_product": row.get("incident_user_still_has_product"),
                "incident_severity": row.get("incident_severity"),
                "exact_upc": row.get("exact_upc", 0),
                "shared_product_token_count": row.get("shared_product_token_count", 0),
                "product_token_jaccard": row.get("product_token_jaccard", 0.0),
                "product_name_sequence_similarity": row.get("product_name_sequence_similarity", 0.0),
                "cpsc_name_token_coverage": row.get("cpsc_name_token_coverage", 0.0),
                "incident_name_token_coverage": row.get("incident_name_token_coverage", 0.0),
                "incident_brand_in_cpsc_name": row.get("incident_brand_in_cpsc_name", 0),
                "incident_model_in_cpsc_name": row.get("incident_model_in_cpsc_name", 0),
                "manufacturer_in_cpsc_name": row.get("manufacturer_in_cpsc_name", 0),
                "blocking_sources": row.get("blocking_sources", []),
                "selection_reason": row.get("selection_reason"),
                "temporal_status": temporal_status(row),
                "similarity_band": similarity_band(float(row.get("product_name_sequence_similarity", 0.0))),
                "jaccard_band": jaccard_band(float(row.get("product_token_jaccard", 0.0))),
                "initial_label": row.get("initial_label", "unlabeled"),
                "review_label": row.get("review_label", ""),
                "reviewer_notes": row.get("reviewer_notes", ""),
            }
        )
    return output


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
            handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False)
                    if isinstance(value, (list, dict))
                    else value
                    for key, value in row.items()
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a stratified evidence-rich CPSC ↔ SaferProducts linkage review set.")
    parser.add_argument("--sample-size", type=int, default=150)
    parser.add_argument("--per-recall-cap", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260918)
    args = parser.parse_args()

    features = load_jsonl(DEFAULT_INPUT)
    candidates = load_jsonl(DEFAULT_CANDIDATES)
    recalls = load_jsonl(DEFAULT_RECALLS)
    incidents = load_jsonl(DEFAULT_INCIDENTS)

    selected = choose_review_rows(features, args.sample_size, args.per_recall_cap, args.seed)
    enriched = join_source_evidence(selected, candidates, recalls, incidents)
    output_rows = prepare_output_rows(enriched)

    write_jsonl(DEFAULT_JSONL, output_rows)
    write_csv(DEFAULT_CSV, output_rows)

    temporal = Counter(row["temporal_status"] for row in output_rows)
    similarity = Counter(row["similarity_band"] for row in output_rows)
    recall_counts = Counter(row["cpsc_source_record_id"] for row in output_rows)
    labels = Counter(row["initial_label"] for row in output_rows)

    manifest = {
        "input_feature_rows": len(features),
        "candidate_rows": len(candidates),
        "selected_rows": len(output_rows),
        "positive_upc_seed_rows": sum(row["initial_label"] == "positive_seed" for row in output_rows),
        "unique_recalls": len(recall_counts),
        "max_rows_per_recall": max(recall_counts.values(), default=0),
        "temporal_distribution": dict(temporal),
        "similarity_distribution": dict(similarity),
        "initial_label_distribution": dict(labels),
        "sampling": {
            "seed": args.seed,
            "requested_sample_size": args.sample_size,
            "per_recall_cap": args.per_recall_cap,
            "selection": "All exact-UPC seeds retained; remaining rows stratified across pre-recall-public, high/medium/low lexical similarity, and two-token candidate strata, then filled deterministically.",
        },
        "human_label_policy": {
            "allowed_labels": list(LABELS),
            "MATCH": "Same underlying product entity/SKU represented by both records.",
            "NON_MATCH": "Different products/entities despite candidate overlap.",
            "UNCERTAIN": "Evidence is insufficient or contradictory for a confident decision.",
        },
        "temporal_policy": "Identity and temporal eligibility are separate; pre_recall_public means incident_date < recall_date and publication_date < recall_date.",
        "evidence_policy": "Review rows are enriched from the canonical CPSC recall, candidate-review, and SaferProducts incident artifacts so labeling is based on source evidence rather than linkage features alone.",
    }
    DEFAULT_MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("SafeSKU human-review linkage set (evidence-enriched)")
    print("----------------------------------------------------")
    print(f"Input feature rows: {len(features)}")
    print(f"Candidate rows: {len(candidates)}")
    print(f"Selected rows: {len(output_rows)}")
    print(f"UPC seeds retained: {manifest['positive_upc_seed_rows']}")
    print(f"Unique recalls represented: {manifest['unique_recalls']}")
    print(f"Max rows per recall: {manifest['max_rows_per_recall']}")
    print(f"Temporal: {dict(temporal)}")
    print(f"Similarity: {dict(similarity)}")
    print(f"CSV: {DEFAULT_CSV}")
    print(f"JSONL: {DEFAULT_JSONL}")
    print(f"Manifest: {DEFAULT_MANIFEST}")


if __name__ == "__main__":
    main()
