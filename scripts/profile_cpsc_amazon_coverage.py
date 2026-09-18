from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize CPSC -> Amazon linkage coverage.")
    parser.add_argument(
        "--candidates",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/candidates.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/coverage_report.json"),
    )
    args = parser.parse_args()

    counts = []
    exact_upc_pairs = 0
    exact_upc_recalls = set()
    recall_to_candidates: dict[str, int] = {}

    with args.candidates.open("r", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            recall = str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or "")
            recall_to_candidates[recall] = recall_to_candidates.get(recall, 0) + 1
            if int(row.get("exact_upc") or 0) == 1:
                exact_upc_pairs += 1
                exact_upc_recalls.add(recall)

    counts = list(recall_to_candidates.values())
    counts_sorted = sorted(counts)

    def percentile(values, p):
        if not values:
            return 0
        index = min(len(values) - 1, int(round((len(values) - 1) * p)))
        return values[index]

    report = {
        "recalls_with_candidates": len(recall_to_candidates),
        "candidate_pairs": len(counts) and sum(counts) or 0,
        "exact_upc_pairs": exact_upc_pairs,
        "exact_upc_recalls": len(exact_upc_recalls),
        "candidate_count_distribution": {
            "min": min(counts) if counts else 0,
            "median": percentile(counts_sorted, 0.50),
            "p90": percentile(counts_sorted, 0.90),
            "max": max(counts) if counts else 0,
        },
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("SafeSKU CPSC -> Amazon coverage")
    print("-------------------------------")
    for key, value in report.items():
        print(f"{key}: {value}")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
