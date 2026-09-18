from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                for key in ("upc", "UPC", "value", "code"):
                    if item.get(key):
                        result.append(str(item[key]))
                        break
        return result
    return []


def norm(value: str) -> str:
    return re.sub(r"\D", "", value)


def extract_cpsc_upcs(path: Path) -> tuple[set[str], Counter[str]]:
    unique: set[str] = set()
    counts: Counter[str] = Counter()

    for recall in read_jsonl(path):
        raw = values(recall.get("product_upcs"))
        for product in recall.get("products") or []:
            if isinstance(product, dict):
                for key in ("upc", "UPC"):
                    if product.get(key):
                        raw.append(str(product[key]))
        for item in raw:
            normalized = norm(item)
            if normalized:
                unique.add(normalized)
                counts[normalized] += 1

    return unique, counts


def extract_amazon_upcs(path: Path) -> tuple[set[str], Counter[str]]:
    unique: set[str] = set()
    counts: Counter[str] = Counter()

    for row in read_jsonl(path):
        normalized = norm(str(row.get("upc") or ""))
        if normalized:
            unique.add(normalized)
            counts[normalized] += 1

    return unique, counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit normalized UPC overlap between CPSC and Amazon.")
    parser.add_argument("--cpsc", type=Path, default=Path("data/benchmark/cpsc/recalls.jsonl"))
    parser.add_argument("--amazon", type=Path, default=Path("data/amazon/normalized/product_metadata.jsonl"))
    parser.add_argument("--candidates", type=Path, default=Path("data/benchmark/amazon_linkage/candidates.jsonl"))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/benchmark/amazon_linkage/identity_overlap_report.json"),
    )
    args = parser.parse_args()

    cpsc_upcs, _ = extract_cpsc_upcs(args.cpsc)
    amazon_upcs, _ = extract_amazon_upcs(args.amazon)
    overlap = sorted(cpsc_upcs & amazon_upcs)

    candidate_counts: Counter[str] = Counter()
    if args.candidates.exists():
        for row in read_jsonl(args.candidates):
            recall = str(row.get("cpsc_recall_number") or row.get("cpsc_source_record_id") or "")
            candidate_counts[recall] += 1

    largest = [
        {"recall": recall, "candidate_pairs": count}
        for recall, count in candidate_counts.most_common(20)
    ]

    report = {
        "cpsc_unique_normalized_upcs": len(cpsc_upcs),
        "amazon_unique_normalized_upcs": len(amazon_upcs),
        "normalized_upc_intersection": len(overlap),
        "intersection_sample": overlap[:50],
        "largest_candidate_recalls": largest,
        "candidate_rows_seen": sum(candidate_counts.values()),
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("SafeSKU CPSC <-> Amazon identity overlap audit")
    print("-----------------------------------------------")
    print(f"CPSC unique normalized UPCs: {report['cpsc_unique_normalized_upcs']}")
    print(f"Amazon unique normalized UPCs: {report['amazon_unique_normalized_upcs']}")
    print(f"Normalized UPC intersection: {report['normalized_upc_intersection']}")
    print()
    print("Largest candidate-producing recalls:")
    for item in largest:
        print(f"  {item['recall']}: {item['candidate_pairs']}")
    print()
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
