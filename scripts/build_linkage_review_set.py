from __future__ import annotations

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/benchmark/linkage/feature_review.jsonl")
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


def parse_date(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def temporal_status(row: dict[str, Any]) -> str:
    recall_date = parse_date(row.get("cpsc_recall_date"))
    incident_date = parse_date(row.get("incident_date"))
    publication_date = parse_date(row.get("publication_date"))

    if not recall_date or not incident_date or not publication_date:
        return "unknown_temporal_status"

    if incident_date < recall_date and publication_date < recall_date:
        return "pre_recall_public"

    if incident_date < recall_date and publication_date >= recall_date:
        return "pre_incident_published_after_recall"

    return "incident_on_or_after_recall"


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


def candidate_strength(row: dict[str, Any]) -> tuple[float, float, int]:
    return (
        float(row.get("product_name_sequence_similarity", 0.0)),
        float(row.get("product_token_jaccard", 0.0)),
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
    """Select deterministically shuffled rows while limiting recall dominance."""
    added = 0
    per_recall = Counter(
        row["cpsc_source_record_id"] for row in selected.values()
    )

    # Prefer stronger candidates first only inside the already-defined stratum.
    ordered = shuffled(pool, rng)
    ordered.sort(key=candidate_strength, reverse=True)

    for row in ordered:
        if added >= count:
            break
        key = row_key(row)
        recall_id = row["cpsc_source_record_id"]
        if key in selected:
            continue
        if per_recall[recall_id] >= per_recall_cap:
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

    # Every exact-UPC seed is retained. They are identity seeds, not automatic
    # ground-truth labels for the whole benchmark.
    seeds = [row for row in rows if row.get("initial_label") == "positive_seed"]
    for row in sorted(seeds, key=row_key):
        selected[row_key(row)] = row

    if len(selected) > sample_size:
        raise ValueError(
            f"sample_size {sample_size} is smaller than the {len(selected)} UPC seeds"
        )

    non_upc = [row for row in rows if row.get("initial_label") != "positive_seed"]

    # The sample is intentionally stratified. This is not a probability estimate
    # over all 3,191 candidates; it is a balanced human-review benchmark.
    strata: list[tuple[str, list[dict[str, Any]], int]] = []

    pre_recall = [
        row for row in non_upc if temporal_status(row) == "pre_recall_public"
    ]
    high = [
        row
        for row in non_upc
        if float(row.get("product_name_sequence_similarity", 0.0)) >= 0.70
        or float(row.get("product_token_jaccard", 0.0)) >= 0.40
    ]
    medium = [
        row
        for row in non_upc
        if row not in high
        and (
            float(row.get("product_name_sequence_similarity", 0.0)) >= 0.40
            or float(row.get("product_token_jaccard", 0.0)) >= 0.15
        )
    ]
    two_token = [
        row for row in non_upc
        if int(row.get("shared_product_token_count", 0)) == 2
    ]
    low = [row for row in non_upc if row not in high and row not in medium]

    # Keep a meaningful number of pre-recall-public pairs because these are the
    # pairs that later participate in the safety lead-time evaluation.
    strata.extend(
        [
            ("pre_recall_public", pre_recall, 30),
            ("high_similarity", high, 35),
            ("medium_similarity", medium, 30),
            ("two_shared_tokens", two_token, 25),
            ("low_similarity", low, 20),
        ]
    )

    for _, pool, target in strata:
        remaining = sample_size - len(selected)
        if remaining <= 0:
            break
        take_from_stratum(
            pool,
            min(target, remaining),
            selected,
            per_recall_cap,
            rng,
        )

    # Fill any remaining quota from the rest of the non-UPC pool, still subject
    # to the recall cap. This keeps the script robust if a stratum is too small.
    remaining = sample_size - len(selected)
    if remaining > 0:
        take_from_stratum(
            non_upc,
            remaining,
            selected,
            per_recall_cap,
            rng,
        )

    chosen = list(selected.values())
    chosen.sort(
        key=lambda row: (
            0 if row.get("initial_label") == "positive_seed" else 1,
            row["cpsc_source_record_id"],
            row["saferproducts_source_record_id"],
        )
    )
    return chosen


def prepare_output_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        output.append(
            {
                "review_id": f"ER-{index:04d}",
                "cpsc_source_record_id": row["cpsc_source_record_id"],
                "cpsc_recall_number": row.get("cpsc_recall_number"),
                "cpsc_recall_date": row.get("cpsc_recall_date"),
                "cpsc_product_name": row.get("cpsc_product_name"),
                "saferproducts_source_record_id": row["saferproducts_source_record_id"],
                "incident_date": row.get("incident_date"),
                "publication_date": row.get("publication_date"),
                "incident_brand": row.get("incident_brand"),
                "incident_model": row.get("incident_model"),
                "incident_upc": row.get("incident_upc"),
                "incident_product_description": row.get(
                    "incident_product_description"
                ),
                "exact_upc": row.get("exact_upc", 0),
                "shared_product_token_count": row.get(
                    "shared_product_token_count", 0
                ),
                "product_token_jaccard": row.get("product_token_jaccard", 0.0),
                "product_name_sequence_similarity": row.get(
                    "product_name_sequence_similarity", 0.0
                ),
                "cpsc_name_token_coverage": row.get("cpsc_name_token_coverage", 0.0),
                "incident_name_token_coverage": row.get(
                    "incident_name_token_coverage", 0.0
                ),
                "incident_brand_in_cpsc_name": row.get(
                    "incident_brand_in_cpsc_name", 0
                ),
                "incident_model_in_cpsc_name": row.get(
                    "incident_model_in_cpsc_name", 0
                ),
                "manufacturer_in_cpsc_name": row.get(
                    "manufacturer_in_cpsc_name", 0
                ),
                "blocking_sources": row.get("blocking_sources", []),
                "selection_reason": row.get("selection_reason"),
                "temporal_status": temporal_status(row),
                "similarity_band": similarity_band(
                    float(row.get("product_name_sequence_similarity", 0.0))
                ),
                "jaccard_band": jaccard_band(
                    float(row.get("product_token_jaccard", 0.0))
                ),
                "initial_label": row.get("initial_label", "unlabeled"),
                "review_label": "",
                "reviewer_notes": "",
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
                    if isinstance(value, list)
                    else value
                    for key, value in row.items()
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a stratified human-reviewed CPSC ↔ SaferProducts linkage set."
    )
    parser.add_argument("--sample-size", type=int, default=150)
    parser.add_argument("--per-recall-cap", type=int, default=2)
    parser.add_argument("--seed", type=int, default=20260918)
    args = parser.parse_args()

    rows = load_jsonl(DEFAULT_INPUT)
    selected = choose_review_rows(
        rows,
        sample_size=args.sample_size,
        per_recall_cap=args.per_recall_cap,
        seed=args.seed,
    )
    output_rows = prepare_output_rows(selected)

    write_jsonl(DEFAULT_JSONL, output_rows)
    write_csv(DEFAULT_CSV, output_rows)

    temporal = Counter(row["temporal_status"] for row in output_rows)
    similarity = Counter(row["similarity_band"] for row in output_rows)
    labels = Counter(row["initial_label"] for row in output_rows)
    recall_counts = Counter(row["cpsc_source_record_id"] for row in output_rows)

    manifest = {
        "input_feature_rows": len(rows),
        "selected_rows": len(output_rows),
        "positive_upc_seed_rows": sum(
            row["initial_label"] == "positive_seed" for row in output_rows
        ),
        "human_label_policy": {
            "allowed_labels": list(LABELS),
            "MATCH": "Same underlying product entity/SKU represented by both records.",
            "NON_MATCH": "Different products/entities despite candidate overlap.",
            "UNCERTAIN": "Evidence is insufficient or contradictory for a confident decision.",
        },
        "sampling": {
            "seed": args.seed,
            "requested_sample_size": args.sample_size,
            "per_recall_cap": args.per_recall_cap,
            "selection": (
                "All exact-UPC seeds retained; remaining rows stratified across "
                "pre-recall-public, high/medium/low lexical similarity, and two-token "
                "candidate strata, then filled deterministically from the non-UPC pool."
            ),
        },
        "initial_label_counts": dict(labels),
        "temporal_status_counts": dict(temporal),
        "similarity_band_counts": dict(similarity),
        "unique_recalls": len(recall_counts),
        "max_rows_per_recall": max(recall_counts.values(), default=0),
        "outputs": {
            "jsonl": str(DEFAULT_JSONL),
            "csv": str(DEFAULT_CSV),
            "manifest": str(DEFAULT_MANIFEST),
        },
    }

    DEFAULT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU human-review linkage set")
    print("--------------------------------")
    print(f"Input feature rows: {len(rows)}")
    print(f"Selected rows: {len(output_rows)}")
    print(f"UPC seeds retained: {manifest['positive_upc_seed_rows']}")
    print(f"Unique recalls represented: {manifest['unique_recalls']}")
    print(f"Max rows per recall: {manifest['max_rows_per_recall']}")
    print(f"Temporal: {dict(temporal)}")
    print(f"Similarity: {dict(similarity)}")
    print(f"JSONL: {DEFAULT_JSONL}")
    print(f"CSV: {DEFAULT_CSV}")
    print(f"Manifest: {DEFAULT_MANIFEST}")


if __name__ == "__main__":
    main()
