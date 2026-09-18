from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


from app.services.linkage.candidates import (
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate auditable CPSC ↔ SaferProducts candidates."
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help=(
            "Number of highest-ranked non-UPC candidates to retain per "
            "recall in the review file. All exact-UPC candidates are "
            "always retained."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.top_k <= 0:
        raise SystemExit("--top-k must be positive.")

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

    upc_index = build_upc_index(incidents)
    token_index = build_token_index(incidents)

    output_path = Path(
        "data/benchmark/linkage/candidate_review.jsonl"
    )
    manifest_path = Path(
        "data/benchmark/linkage/candidate_generation_manifest.json"
    )

    review_rows: list[dict[str, Any]] = []
    candidate_counts: list[int] = []

    exact_upc_candidate_count = 0
    retained_exact_upc_pairs = 0
    recalls_with_candidates = 0

    for recall in recalls:
        candidates = generate_candidates(
            recall,
            incidents_by_id,
            upc_index,
            token_index,
        )

        candidate_counts.append(len(candidates))

        if candidates:
            recalls_with_candidates += 1

        exact_upc_candidates = [
            candidate
            for candidate in candidates
            if candidate.exact_upc
        ]

        exact_upc_candidate_count += len(exact_upc_candidates)

        selected_ids: set[str] = set()

        # Preserve every exact-UPC candidate regardless of top-k.
        for rank, candidate in enumerate(exact_upc_candidates, start=1):
            selected_ids.add(
                candidate.saferproducts_source_record_id
            )

            review_rows.append(
                {
                    **candidate.__dict__,
                    "review_rank": rank,
                    "selection_reason": "retain_exact_upc",
                }
            )

            retained_exact_upc_pairs += 1

        non_upc_rank = 0

        for candidate in candidates:
            if candidate.saferproducts_source_record_id in selected_ids:
                continue

            if non_upc_rank >= args.top_k:
                break

            non_upc_rank += 1
            selected_ids.add(candidate.saferproducts_source_record_id)

            review_rows.append(
                {
                    **candidate.__dict__,
                    "review_rank": (
                        len(exact_upc_candidates) + non_upc_rank
                    ),
                    "selection_reason": (
                        "top_ranked_non_upc_candidate"
                    ),
                }
            )

    review_rows.sort(
        key=lambda row: (
            row["cpsc_source_record_id"],
            row["review_rank"],
            row["saferproducts_source_record_id"],
        )
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as handle:
        for row in review_rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            handle.write("\n")

    ordered = sorted(candidate_counts)

    def percentile(p: float) -> int:
        if not ordered:
            return 0

        index = min(
            len(ordered) - 1,
            max(0, int(p * len(ordered)) - 1),
        )

        return ordered[index]

    report = {
        "cpsc_recall_count": len(recalls),
        "saferproducts_incident_count": len(incidents),
        "blocking_union": [
            "exact_upc",
            "shared_2plus_product_tokens",
        ],
        "review_non_upc_top_k_per_recall": args.top_k,
        "recalls_with_at_least_one_candidate": recalls_with_candidates,
        "candidate_count_min": min(candidate_counts, default=0),
        "candidate_count_median": (
            ordered[len(ordered) // 2]
            if ordered
            else 0
        ),
        "candidate_count_p90": percentile(0.90),
        "candidate_count_max": max(candidate_counts, default=0),
        "exact_upc_candidates": exact_upc_candidate_count,
        "retained_exact_upc_pairs": retained_exact_upc_pairs,
        "review_rows": len(review_rows),
        "candidate_review_file": str(output_path),
        "blocking_policy": (
            "Exact UPC candidates are always retained. "
            "Additional review candidates are selected by transparent "
            "ranking from the >=2 product-name-token blocker."
        ),
        "note": (
            "candidate_review.jsonl is a review artifact, not the complete "
            "candidate set. The complete candidate set is generated in "
            "memory by generate_candidates()."
        ),
    }

    manifest_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ) + "\n",
        encoding="utf-8",
    )

    print("SafeSKU CPSC ↔ SaferProducts candidate generation")
    print("-------------------------------------------------")
    print(f"CPSC recalls: {len(recalls)}")
    print(f"SaferProducts incidents: {len(incidents)}")
    print(
        "Recalls with candidates: "
        f"{recalls_with_candidates}/{len(recalls)}"
    )
    print(
        "Candidate count: "
        f"min={report['candidate_count_min']} "
        f"median={report['candidate_count_median']} "
        f"p90={report['candidate_count_p90']} "
        f"max={report['candidate_count_max']}"
    )
    print(f"Exact UPC candidates: {exact_upc_candidate_count}")
    print(f"Retained exact UPC pairs: {retained_exact_upc_pairs}")
    print(f"Review rows: {len(review_rows)}")
    print(f"Review file: {output_path}")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
