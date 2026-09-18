from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from app.services.linkage.candidates import (
    CandidatePair,
    build_token_index,
    build_upc_index,
    generate_candidates,
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def candidate_from_dict(row: dict[str, Any]) -> CandidatePair:
    return CandidatePair(
        cpsc_source_record_id=row["cpsc_source_record_id"],
        cpsc_recall_number=row.get("cpsc_recall_number"),
        cpsc_recall_date=row.get("cpsc_recall_date"),
        cpsc_product_name=row.get("cpsc_product_name"),
        saferproducts_source_record_id=(
            row["saferproducts_source_record_id"]
        ),
        blocking_sources=tuple(row.get("blocking_sources", [])),
        exact_upc=bool(row.get("exact_upc")),
        shared_product_tokens=tuple(
            row.get("shared_product_tokens", [])
        ),
        shared_product_token_count=int(
            row.get("shared_product_token_count", 0)
        ),
        product_token_jaccard=float(
            row.get("product_token_jaccard", 0.0)
        ),
        incident_date=row.get("incident_date"),
        publication_date=row.get("publication_date"),
        incident_brand=row.get("incident_brand"),
        incident_model=row.get("incident_model"),
        incident_upc=row.get("incident_upc"),
        incident_product_description=row.get(
            "incident_product_description"
        ),
    )


def main() -> None:
    from app.services.linkage.features import build_pair_features

    recalls = load_jsonl(
        Path("data/benchmark/cpsc/recalls.jsonl")
    )
    incidents = load_jsonl(
        Path("data/benchmark/saferproducts/incidents.jsonl")
    )

    incidents_by_id = {
        incident["source_record_id"]: incident
        for incident in incidents
    }

    recalls_by_id = {
        recall["source_record_id"]: recall
        for recall in recalls
    }

    review_path = Path(
        "data/benchmark/linkage/candidate_review.jsonl"
    )

    if not review_path.exists():
        raise SystemExit(
            "candidate_review.jsonl not found. "
            "Run generate_cpsc_saferproducts_candidates.py first."
        )

    candidate_rows = load_jsonl(review_path)

    feature_rows: list[dict[str, Any]] = []
    seed_count = 0
    unlabeled_count = 0

    for row in candidate_rows:
        recall = recalls_by_id[row["cpsc_source_record_id"]]
        incident = incidents_by_id[
            row["saferproducts_source_record_id"]
        ]
        candidate = candidate_from_dict(row)

        features = build_pair_features(
            candidate,
            recall,
            incident,
        )

        is_seed = features.exact_upc == 1
        label = "positive_seed" if is_seed else "unlabeled"

        feature_rows.append(
            {
                **features.dict,
                "blocking_sources": list(
                    candidate.blocking_sources
                ),
                "selection_reason": row.get("selection_reason"),
                "review_rank": row.get("review_rank"),
                "initial_label": label,
            }
        )

        if is_seed:
            seed_count += 1
        else:
            unlabeled_count += 1

    output_path = Path(
        "data/benchmark/linkage/feature_review.jsonl"
    )
    manifest_path = Path(
        "data/benchmark/linkage/feature_review_manifest.json"
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for row in feature_rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            handle.write("\n")

    jaccards = [
        row["product_token_jaccard"]
        for row in feature_rows
    ]

    similarities = [
        row["product_name_sequence_similarity"]
        for row in feature_rows
    ]

    counts = Counter(
        row["shared_product_token_count"]
        for row in feature_rows
    )

    manifest = {
        "source_candidate_rows": len(candidate_rows),
        "feature_rows": len(feature_rows),
        "positive_seed_rows": seed_count,
        "unlabeled_rows": unlabeled_count,
        "shared_token_count_distribution": {
            str(k): v
            for k, v in sorted(counts.items())
        },
        "product_token_jaccard": {
            "min": min(jaccards, default=0.0),
            "median": (
                statistics.median(jaccards)
                if jaccards
                else 0.0
            ),
            "max": max(jaccards, default=0.0),
        },
        "product_name_sequence_similarity": {
            "min": min(similarities, default=0.0),
            "median": (
                statistics.median(similarities)
                if similarities
                else 0.0
            ),
            "max": max(similarities, default=0.0),
        },
        "label_policy": (
            "Exact UPC candidates are marked positive_seed. "
            "All non-UPC candidates remain unlabeled and require "
            "human review. No automatic negative labels are created."
        ),
    }

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU linkage feature review")
    print("-------------------------------")
    print(f"Candidate rows: {len(candidate_rows)}")
    print(f"Feature rows: {len(feature_rows)}")
    print(f"Positive UPC seeds: {seed_count}")
    print(f"Unlabeled rows: {unlabeled_count}")
    print(
        "Jaccard: "
        f"min={manifest['product_token_jaccard']['min']:.4f} "
        f"median={manifest['product_token_jaccard']['median']:.4f} "
        f"max={manifest['product_token_jaccard']['max']:.4f}"
    )
    print(
        "Sequence similarity: "
        f"min={manifest['product_name_sequence_similarity']['min']:.4f} "
        f"median={manifest['product_name_sequence_similarity']['median']:.4f} "
        f"max={manifest['product_name_sequence_similarity']['max']:.4f}"
    )
    print(f"Feature review: {output_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
